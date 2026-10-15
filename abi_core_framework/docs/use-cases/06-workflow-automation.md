# Workflow Automation & Orchestration

Many agentic systems try to automate a business process by handing the whole thing to a model: here are the tools, here's the email, figure it out. It reads well in a demo. In operations it looks like this — an illustration, not any real product:

```
Ops:  Did the BrightFreight order go through?
Bot:  Yes! I created the invoice, emailed the customer and updated inventory. 🎉
Ops:  Finance says there are two invoices for PO 4471.
Bot:  You're right — I retried when the email failed. I've voided one of them.
Ops:  Which one? And why does the total have no tax?
Bot:  I calculated the total from the order information provided.
```

A retry that billed twice. An email that half-failed. A total nobody can reproduce.

I'm ABI, and in a workflow the model gets exactly one job: reading the free text nobody formatted for a machine. Everything else is code you can read: the checks run in parallel and all must pass, prices come from the catalog, a purchase order is billed once, and the slow, flaky email goes to the background where the framework retries it on its own. Here's a real run:

```
>>> Hi team, BrightFreight here. Please send 3 espresso machines and 10 bags of the 1kg arabica beans ...
Invoice INV-00001 created for BrightFreight (PO 4471).
- 3 × Espresso machine @ $249.00 = $747.00
- 10 × Arabica beans 1kg @ $24.00 = $240.00
Subtotal $987.00 · tax $157.92 · total $1,144.92
The customer email is being sent in the background — ask `status INV-00001`.

>>> status INV-00001
Email for INV-00001 sent — the email API answered on call 3.

>>> (the same order email, again)
PO 4471 was already invoiced as INV-00001. Nothing was done twice.

>>> Hi, this is TinyShop. We'd like 20 ceramic mugs please. PO 9001. — Marco
I stopped before billing anything:
- TinyShop is on credit hold.
- Not enough stock: Ceramic mug.
```

It takes about twenty-five minutes to build.

## What you'll build

One agent, `orders`, that runs an order-to-invoice process:

```
order email ──▶ read the order (model → customer, PO, lines)
            ──▶ PO already billed? stop (code)
            ──▶ in parallel ──┬─ CRM: known customer, credit OK?   ─┐
                              ├─ inventory: in catalog, in stock?  ─┼─▶ all OK? (code)
                              └─ pricing: catalog price + tax      ─┘     │
                                                                          ├─ no  ──▶ stop, list every problem
                                                                          └─ yes ──▶ ERP invoice
                                                                                 ──▶ email in the background,
                                                                                     retried with backoff
```

ABI features on this page: `asyncio.gather` over steps for [parallel work](../orchestration/03-dependency-management.md#programmatic-parallelism-in-tasks), [`@agent.task_async`](../production/06-background-and-scheduled-tasks.md) with automatic retries and status lookup, [run progress](../single-agent/11-run-progress.md) phases in the chat, and `invoke_structured`.

## Step 1: Create the project and the agent

```bash
abi-core create project --name ops
cd ops
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name orders \
  --description "Turns order emails into invoices: checks the customer, stock and price, bills, and notifies" \
  --with-web-interface
```

When it asks for tasks/skills, type `process_order`. Press Enter for the URL.

## Step 2: The systems

A CRM, an inventory, a catalog, an ERP and an email service — each a small async function, so replacing one with the real API touches nothing else. The email service fails twice per invoice on purpose.

Create `agents/orders/systems.py`:

```python
"""Stand-ins for the systems a real workflow connects. Each one is a small async
function, so swapping in the real API is a one-function change."""

import asyncio

CATALOG = {  # product → unit price
    "Espresso machine": 249.0, "Coffee grinder": 89.0, "Arabica beans 1kg": 24.0, "Ceramic mug": 12.0,
}
TAX_RATE = 0.16

_CRM = {"BrightFreight": {"customer_id": "C-0042", "email": "purchasing@brightfreight.io", "credit_ok": True},
        "TinyShop": {"customer_id": "C-0107", "email": "marco@tinyshop.it", "credit_ok": False}}
_STOCK = {"Espresso machine": 5, "Coffee grinder": 12, "Arabica beans 1kg": 200, "Ceramic mug": 0}
INVOICES = {}           # the ERP: invoice id → invoice
_email_attempts = {}    # how many times the email API was called per invoice


async def crm_lookup(customer):
    await asyncio.sleep(0.5)  # a network call
    return _CRM.get(customer)


def crm_accounts_named_in(text):
    """CRM accounts whose name appears in the text. In production you'd match the sender's address."""
    return [name for name in _CRM if name.lower() in text.lower()]


async def inventory_check(items):
    await asyncio.sleep(0.5)
    return {i["product"]: _STOCK.get(i["product"], 0) >= i["quantity"] for i in items}


async def erp_create_invoice(customer_id, po_number, lines, total):
    await asyncio.sleep(0.5)
    invoice_id = f"INV-{len(INVOICES) + 1:05d}"
    INVOICES[invoice_id] = {"customer_id": customer_id, "po": po_number, "lines": lines, "total": total}
    return invoice_id


async def email_send(to, subject, body, key):
    """A flaky email API: the first two calls for each invoice fail."""
    await asyncio.sleep(0.3)
    _email_attempts[key] = _email_attempts.get(key, 0) + 1
    if _email_attempts[key] <= 2:
        raise ConnectionError("email service timed out")
    return {"to": to, "subject": subject, "attempt": _email_attempts[key]}
```

## Step 3: What the model may extract

Replace the contents of `agents/orders/models.py`:

```python
"""What the model may pull out of an order email."""

from typing import List

from pydantic import BaseModel, Field


class OrderLine(BaseModel):
    product: str = Field(description="Product name exactly as written in the catalog")
    quantity: int = Field(description="How many units")


class Order(BaseModel):
    customer: str = Field(description="The ordering company's name")
    po_number: str = Field(description="Purchase order number, digits only; empty if none")
    items: List[OrderLine] = Field(description="Every product ordered")
```

## Step 4: The prompt

Create `agents/orders/prompts.py`:

```python
EXTRACT_PROMPT = """Extract the order from this email.
Catalog products (use these exact names): {catalog}
If a product isn't in the catalog, write it as the customer did.

Email:
{email}"""
```

## Step 5: The steps

One step reads text. The other five are code — including the one that decides who the customer is: an account name that appears in the email beats the model's reading. (qwen3 kept reading "Marco" as the customer of "Hi, this is TinyShop … — Marco"; in production you'd match the sender's address.)

Replace the contents of `agents/orders/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke_structured
from models import Order
from prompts import EXTRACT_PROMPT
from systems import CATALOG, TAX_RATE, crm_accounts_named_in, crm_lookup, erp_create_invoice, inventory_check


@agent.step(name="extract_order")
async def extract_order(email):
    """The only step that needs a model: reading free text."""
    order = await invoke_structured(
        config.LLM_CONFIG, EXTRACT_PROMPT.format(catalog=", ".join(CATALOG), email=email), Order
    )
    return order.model_dump()


@agent.step(name="validate_customer")
async def validate_customer(customer, email):
    """Who the customer is, code decides: a CRM account named in the email wins over the model's guess."""
    named = crm_accounts_named_in(email)
    customer = named[0] if len(named) == 1 else customer
    record = await crm_lookup(customer)
    if not record:
        return {"ok": False, "problem": f"{customer} isn't a customer in the CRM."}
    if not record["credit_ok"]:
        return {"ok": False, "problem": f"{customer} is on credit hold."}
    return {"ok": True, "customer": customer, **record}


@agent.step(name="check_stock")
async def check_stock(items):
    unknown = [i["product"] for i in items if i["product"] not in CATALOG]
    if unknown:
        return {"ok": False, "problem": f"Not in the catalog: {', '.join(unknown)}."}
    available = await inventory_check(items)
    short = [product for product, ok in available.items() if not ok]
    return {"ok": not short, "problem": f"Not enough stock: {', '.join(short)}." if short else ""}


@agent.step(name="price_order")
async def price_order(items):
    """Arithmetic is code. Prices come from the catalog, never from the email or the model."""
    lines = [{**i, "unit_price": CATALOG.get(i["product"], 0.0),
              "amount": round(CATALOG.get(i["product"], 0.0) * i["quantity"], 2)} for i in items]
    subtotal = round(sum(line["amount"] for line in lines), 2)
    return {"lines": lines, "subtotal": subtotal, "tax": round(subtotal * TAX_RATE, 2),
            "total": round(subtotal * (1 + TAX_RATE), 2)}


@agent.step(name="create_invoice")
async def create_invoice(customer_id, po_number, lines, total):
    return {"invoice_id": await erp_create_invoice(customer_id, po_number, lines, total)}
```

## Step 6: The task

The process, in order, in plain Python. `asyncio.gather` runs the three checks at once; `execute_task_async` hands the email to the background and returns right away.

Replace the contents of `agents/orders/tasks.py`:

```python
import asyncio
import re

from app import agent
from abi_core.agent.agent_response import AgentResponse, RunPhase
from systems import email_send

INVOICED_POS = {}  # po_number → invoice id. In production: a unique key in your ERP.


@agent.task_async(name="notify_customer", max_retries=3, base_delay=2.0)
async def notify_customer(email, invoice_id, total):
    """Runs in the background. If the email API fails, the framework retries with backoff."""
    return await email_send(email, f"Invoice {invoice_id}", f"Total: ${total:,.2f}", key=invoice_id)


@agent.task(name="process_order", task_id="task-process-order")
async def process_order(query, context_id=None):
    # "status INV-00001" → how is the email for that invoice doing?
    asked = re.search(r"\bINV-\d{5}\b", query.upper())
    if query.lower().startswith("status") and asked:
        session = await agent.get_session_context(context_id)
        job = (session.get("notifications") or {}).get(asked.group(0))
        status = await agent.get_async_task_status(job) if job else None
        if not status:
            yield AgentResponse.text(f"I don't know invoice {asked.group(0)}.")
        elif status["status"] == "done":
            calls = status["result"]["attempt"]
            yield AgentResponse.text(f"Email for {asked.group(0)} sent — the email API answered on call {calls}.")
        else:
            yield AgentResponse.text(f"Email for {asked.group(0)}: {status['status']}.")
        return

    # 1. Read the email (model).
    def progress(text, step):
        return AgentResponse.status(text, phase=RunPhase.EXECUTING.value, phase_detail=step)

    yield progress("Reading the order...", "Extracting the order from the email")
    order = await agent.execute_step("extract_order", email=query)
    po = re.sub(r"\D", "", order["po_number"])
    if po and po in INVOICED_POS:
        yield AgentResponse.text(f"PO {po} was already invoiced as {INVOICED_POS[po]}. Nothing was done twice.")
        return

    # 2. Three independent checks, at the same time (code + APIs).
    yield progress("Checking customer, stock and price...", "CRM, inventory and pricing in parallel")
    customer, stock, price = await asyncio.gather(
        agent.execute_step("validate_customer", customer=order["customer"], email=query),
        agent.execute_step("check_stock", items=order["items"]),
        agent.execute_step("price_order", items=order["items"]),
    )

    # 3. All or nothing: if any check fails, no invoice and no email.
    problems = [c["problem"] for c in (customer, stock) if not c["ok"]]
    if problems:
        yield AgentResponse.text("I stopped before billing anything:\n\n- " + "\n- ".join(problems))
        return

    # 4. Bill it.
    yield progress("Creating the invoice...", "Writing the invoice to the ERP")
    invoice = await agent.execute_step(
        "create_invoice", customer_id=customer["customer_id"], po_number=po,
        lines=price["lines"], total=price["total"],
    )
    invoice_id = invoice["invoice_id"]
    if po:
        INVOICED_POS[po] = invoice_id

    # 5. Notify in the background; the email API is slow and flaky, the user doesn't wait for it.
    job = await agent.execute_task_async(
        "notify_customer", context_id=context_id, email=customer["email"], invoice_id=invoice_id, total=price["total"]
    )
    session = await agent.get_session_context(context_id)
    await agent.update_session_context(
        context_id, {"notifications": {**(session.get("notifications") or {}), invoice_id: job}}
    )

    lines = "\n".join(f"- {l['quantity']} × {l['product']} @ ${l['unit_price']:,.2f} = ${l['amount']:,.2f}"
                      for l in price["lines"])
    yield AgentResponse.text(
        f"Invoice **{invoice_id}** created for {customer['customer']} (PO {po or '—'}).\n\n{lines}\n\n"
        f"Subtotal ${price['subtotal']:,.2f} · tax ${price['tax']:,.2f} · **total ${price['total']:,.2f}**\n\n"
        f"The customer email is being sent in the background — ask `status {invoice_id}`."
    )
```

## Step 7: Run it

In `compose.yaml`, add to the `environment` of the `ops-orders` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Then:

```bash
abi-core add chainlit
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 8: Use it

Open **http://localhost:8500** and paste an order email. While it works, the progress step shows each stage — reading the order, the three checks, the invoice. Then ask `status INV-00001`, wait a few seconds, and ask again. Paste the same email twice and see what happens.

In the agent's logs, each background attempt is recorded:

```bash
docker compose logs ops-orders | grep TASK_ASYNC_AUDIT
```

### Or from a script

Save this as `orders.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

ORDER = """Hi team, BrightFreight here. Please send 3 espresso machines and
10 bags of the 1kg arabica beans to our Monterrey warehouse. Our PO is #4471.
Thanks, Dana"""

HELD = "Hi, this is TinyShop. We'd like 20 ceramic mugs please. PO 9001. — Marco"


async def say(client, message):
    print(f"\n>>> {message.splitlines()[0]}")
    async for event in client.stream(message):
        if event.get("is_task_completed") or event.get("response_type") == "error":
            print(event.get("content"))


async def main():
    client = AgentStreamClient("http://localhost:8002")
    await say(client, ORDER)
    await say(client, "status INV-00001")
    await asyncio.sleep(10)            # give the background email time to retry
    await say(client, "status INV-00001")
    await say(client, ORDER)           # the same PO again
    await say(client, HELD)

asyncio.run(main())
```

```bash
python orders.py
```

On a laptop CPU with `qwen3:latest`, each order took 10 to 20 seconds — almost all of it reading the email. The checks and the invoice are milliseconds plus the mock APIs' half-second sleeps.

## What happened

1. **The BrightFreight email.** The model read three things: the customer, `#4471`, and two order lines with catalog names. Code stripped the PO to digits and checked it hadn't been billed.
2. **Three checks, at once.** The CRM, the inventory and the pricing ran in parallel. All passed, so the ERP created `INV-00001` with a total code computed from catalog prices and the tax rate.
3. **The email, in the background.** The chat answered right away. Behind it, the email API failed, the framework waited and retried, it failed again, waited longer, and the third call went through — `status INV-00001` shows it.
4. **The same email again.** PO 4471 was already billed: nothing ran, nothing was billed twice.
5. **TinyShop.** Code named the customer from the CRM, found the credit hold, and the inventory found no mugs. Both problems were reported together, and no invoice or email was created — all or nothing.

What the model never did: compute a price, decide whether a check passed, bill, or retry anything.

## Before you run real orders through it

- **Connect the real systems.** Each function in `systems.py` is one API call; keep their signatures and swap the bodies.
- **Make "billed once" a database guarantee.** `INVOICED_POS` lives in memory; in production, a unique key on the PO in your ERP or database.
- **Keep background status beyond a restart.** Set `ASYNC_TASK_BACKEND=redis` so `status` works across restarts and replicas — see [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md).
- **Identify customers by sender**, not by text: map the email's from-address to the CRM account.
- **Add an approval step for large orders** with the [plan confirmation](../single-agent/09-plan-confirmation.md) building block, as in [Lead Qualification](03-lead-qualification.md).

## Next

👉 Back to [Use Cases](index.md)
