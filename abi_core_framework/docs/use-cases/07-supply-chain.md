# Supply Chain & Logistics Optimization

Many agentic systems treat planning as a conversation: describe the warehouse, ask what to buy, trust the number that comes back. It sounds like an analyst. It counts like a coin toss — an illustration, not any real product:

```
Planner: What should I reorder this week?
Bot:     Order 250 espresso machines — demand is surging! 📈
Planner: We sold about two a day last month.
Bot:     Good point! Revised recommendation: 12 espresso machines.
Planner: And the 24 machines stuck in customs?
Bot:     I've included them as arriving on schedule.
```

Two different answers to the same question. A shipment counted that isn't coming. And no way to see the math.

I'm ABI, and a reorder quantity is arithmetic, so code does it — the same way every time: a demand forecast from real sales, the days of cover, a reorder point with safety stock, an order rounded to full cases, and a shipment on customs hold simply doesn't count. The model gets the part where a person wants words: *why*. It explains the plan; it can't change a single number. Here's an excerpt from a real run:

```
>>> What should I reorder this week?
  reorder  Cold brew kit      cover   14.0 d  order 102
  reorder  Espresso machine   cover   18.7 d  order 48
  watch    Arabica beans 1kg  cover   16.4 d  order 0
  ok       Coffee grinder     cover   38.2 d  order 0
  ok       Ceramic mug        cover  196.0 d  order 0
You should reorder 102 units of Cold brew kit and 48 units of Espresso machine this week.
The Arabica beans 1kg is under watch but no order is needed. ...

Shipments at risk
- SH-302 (Espresso machine, 24 units): carrier reports customs hold
- SH-303 (Coffee grinder, 36 units): 2 days past its ETA

>>> Why does the cold brew kit need an order? Sales were low last month.
The cold brew kit needs an order because the reorder point is 102, and the current stock is 70.
The daily forecast is 5.0 units, which means the kit will run out of stock in 14 days.
Sales were higher last week than the 4-week average, indicating increased demand.
```

It takes about twenty minutes to build.

## What you'll build

One agent, `inventory`, that recomputes the plan on every question and every morning:

```
shipments ──▶ on hold, exception or past ETA? → at risk, not counted (code)
sales     ──▶ forecast = higher of the 4-week and last-week daily average (code)
stock     ──▶ days of cover, reorder point, order rounded to cases (code)
          ──▶ plan table in the chat
question  ──▶ the model explains, using only the table and the alerts
07:00     ──▶ the same plan, on its own
```

ABI features on this page: a plan rendered as a [table](../single-agent/10-rich-elements.md) in the chat, and [`@agent.task_schedule`](../production/06-background-and-scheduled-tasks.md) for the morning check.

## Step 1: Create the project and the agent

```bash
abi-core create project --name supply
cd supply
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name inventory \
  --description "Watches inventory and shipments, forecasts demand and recommends what to reorder" \
  --with-web-interface
```

When it asks for tasks/skills, type `plan_inventory`. Press Enter for the URL.

The morning check needs the scheduler. Add this line to `agents/inventory/requirements.txt`:

```
abi-core-ai[scheduler]
```

## Step 2: The warehouse

Five products, four inbound shipments and four weeks of sales — generated relative to today, so the tutorial works any day. Cold brew kits have just started selling three times faster.

Create `agents/inventory/warehouse.py`:

```python
"""Sample warehouse data, generated relative to today. In production: your WMS/ERP and your carriers' APIs."""

import random
from datetime import date, timedelta

TODAY = date.today()

# stock on hand, supplier lead time, safety stock, units per case, typical units sold per day
PRODUCTS = {
    "Espresso machine":  {"stock": 40,  "lead_time_days": 21, "safety_stock": 10, "case_size": 4,  "rate": 2.0},
    "Coffee grinder":    {"stock": 120, "lead_time_days": 14, "safety_stock": 15, "case_size": 6,  "rate": 3.0},
    "Arabica beans 1kg": {"stock": 300, "lead_time_days": 10, "safety_stock": 60, "case_size": 20, "rate": 25.0},
    "Ceramic mug":       {"stock": 900, "lead_time_days": 30, "safety_stock": 50, "case_size": 36, "rate": 6.0},
    "Cold brew kit":     {"stock": 70,  "lead_time_days": 18, "safety_stock": 12, "case_size": 6,  "rate": 1.5},
}

INBOUND = [
    {"id": "SH-301", "product": "Arabica beans 1kg", "units": 200, "eta": TODAY + timedelta(days=4),
     "carrier_status": "in_transit"},
    {"id": "SH-302", "product": "Espresso machine", "units": 24, "eta": TODAY + timedelta(days=9),
     "carrier_status": "customs_hold"},
    {"id": "SH-303", "product": "Coffee grinder", "units": 36, "eta": TODAY - timedelta(days=2),
     "carrier_status": "in_transit"},
    {"id": "SH-304", "product": "Ceramic mug", "units": 360, "eta": TODAY + timedelta(days=20),
     "carrier_status": "in_transit"},
]


def sales_history(days=28):
    """Units sold per day, oldest first. Same seed, same history. Cold brew kits
    are taking off: the last week sells three times the usual rate."""
    rnd = random.Random(7)
    history = {}
    for name, p in PRODUCTS.items():
        daily = []
        for day in range(days):
            rate = p["rate"] * (3 if name == "Cold brew kit" and day >= days - 7 else 1)
            daily.append(max(0, round(rnd.gauss(rate, rate * 0.3))))
        history[name] = daily
    return history
```

## Step 3: The prompt

Create `agents/inventory/prompts.py`:

```python
EXPLAIN_PROMPT = """You are an inventory planner's assistant. Answer the question in plain language,
in at most four sentences, using ONLY the numbers in the plan and the shipment alerts below.
Don't change any number and don't recommend quantities that aren't in the plan.

Plan (one row per product):
{plan}

Shipment alerts:
{alerts}

Question: {question}"""
```

## Step 4: The steps

`check_shipments` and `build_plan` are the whole planning logic, and neither calls a model. Change a rule — the safety stock, the review period, what counts as late — and every number changes with it, predictably.

Replace the contents of `agents/inventory/steps.py`:

```python
import json
import math

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from prompts import EXPLAIN_PROMPT
from warehouse import INBOUND, PRODUCTS, TODAY, sales_history

REVIEW_DAYS = 14  # an order should cover the lead time plus two weeks


@agent.step(name="check_shipments")
async def check_shipments():
    """Rules, not guesses: a hold, an exception or a missed ETA means the shipment can't be counted on."""
    alerts = []
    for s in INBOUND:
        if s["carrier_status"] in ("customs_hold", "exception"):
            alerts.append({**s, "risk": f"carrier reports {s['carrier_status'].replace('_', ' ')}"})
        elif s["carrier_status"] != "delivered" and s["eta"] < TODAY:
            alerts.append({**s, "risk": f"{(TODAY - s['eta']).days} days past its ETA"})
    return {"alerts": [{**a, "eta": str(a["eta"])} for a in alerts]}


@agent.step(name="build_plan")
async def build_plan(alerts):
    """Forecast, cover and reorder quantity for every product. Plain arithmetic."""
    at_risk = {a["id"] for a in alerts}
    history = sales_history()
    rows = []
    for name, p in PRODUCTS.items():
        sold = history[name]
        avg_4w, avg_1w = sum(sold) / 28, sum(sold[-7:]) / 7
        forecast = max(avg_4w, avg_1w)  # a rising product isn't under-forecast
        # Only shipments that are on track and arrive within the lead time count.
        inbound = sum(s["units"] for s in INBOUND
                      if s["product"] == name and s["id"] not in at_risk
                      and (s["eta"] - TODAY).days <= p["lead_time_days"])
        projected = p["stock"] + inbound
        reorder_point = forecast * p["lead_time_days"] + p["safety_stock"]
        cover = projected / forecast if forecast else math.inf
        if projected <= reorder_point:
            status = "reorder"
            need = forecast * (p["lead_time_days"] + REVIEW_DAYS) + p["safety_stock"] - projected
            order = math.ceil(need / p["case_size"]) * p["case_size"]
        else:
            status = "watch" if cover < p["lead_time_days"] + 7 else "ok"
            order = 0
        rows.append({
            "Product": name, "Stock": p["stock"], "Inbound": inbound,
            "Avg/day 4 weeks": round(avg_4w, 1), "Avg/day last week": round(avg_1w, 1),
            "Daily forecast": round(forecast, 1), "Days of cover": round(cover, 1),
            "Reorder point": round(reorder_point), "Status": status, "Order": order,
        })
    order_rank = {"reorder": 0, "watch": 1, "ok": 2}
    return {"plan": sorted(rows, key=lambda r: (order_rank[r["Status"]], r["Days of cover"]))}


@agent.step(name="explain")
async def explain(question, plan, alerts):
    """The model explains the plan. It can't change it."""
    reply = await invoke(config.LLM_CONFIG, EXPLAIN_PROMPT.format(
        plan=json.dumps(plan, indent=1), alerts=json.dumps(alerts, indent=1) if alerts else "none",
        question=question,
    ))
    return {"answer": reply}
```

## Step 5: The task and the morning check

Replace the contents of `agents/inventory/tasks.py`:

```python
from datetime import datetime, timezone

from app import agent
from abi_core.agent.agent_response import AgentResponse

LAST_CHECK = {}  # the daily job's latest result


@agent.task(name="plan_inventory", task_id="task-plan-inventory")
async def plan_inventory(query, context_id=None):
    yield AgentResponse.status("Checking shipments and stock...")
    alerts = (await agent.execute_step("check_shipments"))["alerts"]
    plan = (await agent.execute_step("build_plan", alerts=alerts))["plan"]

    yield AgentResponse.element("dataframe", {"data": plan}, name="Inventory plan")
    answer = (await agent.execute_step("explain", question=query, plan=plan, alerts=alerts))["answer"]

    flagged = "\n".join(f"- {a['id']} ({a['product']}, {a['units']} units): {a['risk']}" for a in alerts)
    last = f"\n\n_Last automatic check: {LAST_CHECK['at']} — {LAST_CHECK['reorder']} to reorder._" if LAST_CHECK else ""
    yield AgentResponse.text(answer + (f"\n\n**Shipments at risk**\n{flagged}" if alerts else "") + last)


@agent.task_schedule(name="daily_check", trigger="cron", trigger_args={"hour": 7, "minute": 0})
async def daily_check():
    """Every morning at 7, with nobody asking. In production: send the reorder list to purchasing."""
    alerts = (await agent.execute_step("check_shipments"))["alerts"]
    plan = (await agent.execute_step("build_plan", alerts=alerts))["plan"]
    LAST_CHECK.update({
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "reorder": ", ".join(r["Product"] for r in plan if r["Status"] == "reorder") or "nothing",
    })
    return LAST_CHECK
```

## Step 6: Run it

In `compose.yaml`, add to the `environment` of the `supply-inventory` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Then:

```bash
abi-core add chainlit
docker volume create ollama_data              # once per machine; `abi-core run` also creates it
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 7: Use it

Open **http://localhost:8500** and ask "What should I reorder this week?" The plan appears as a table, then the explanation and the shipments at risk. Ask *why* about any row — and try giving it a wrong premise, like "sales were low last month".

The morning check runs at 07:00 in the container's time zone (UTC, unless you set `TZ`); after it has run, every answer ends with its result.

### Or from a script

Save this as `plan.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

QUESTIONS = [
    "What should I reorder this week?",
    "Why does the cold brew kit need an order? Sales were low last month.",
    "Which shipments should I worry about?",
]


async def main():
    client = AgentStreamClient("http://localhost:8002")
    for question in QUESTIONS:
        print(f"\n>>> {question}")
        async for event in client.stream(question):
            if event.get("response_type") == "element":
                for row in event["content"]["props"]["data"]:
                    print(f"  {row['Status']:<8} {row['Product']:<18} cover {row['Days of cover']:>6} d"
                          f"  order {row['Order']}")
            elif event.get("is_task_completed") or event.get("response_type") == "error":
                print(event.get("content"))

asyncio.run(main())
```

```bash
python plan.py
```

On a laptop CPU with `qwen3:latest`, each question took 8 to 30 seconds — all of it the explanation. The plan itself is computed in milliseconds.

## What happened

1. **Shipments first.** SH-302 is on customs hold and SH-303 is two days past its ETA, so neither counts as inbound. The 24 espresso machines in customs don't exist for planning until they move.
2. **Cold brew kit: reorder 102.** Last week sold well above the 4-week average, so the forecast uses last week's rate — 5 a day. Seventy in stock is below the reorder point of 102 (5 a day × 18 days of lead time + 12 safety), so code orders enough for the lead time plus two weeks, rounded up to cases of 6.
3. **Espresso machine: reorder 48.** Without the held shipment, 40 units fall under the reorder point.
4. **"Sales were low last month."** In two of my three runs the model pointed at the table — last week ran above the 4-week average — and disagreed with the premise; in the third it explained the reorder point and let the premise pass. Either way the order stayed at 102: the numbers aren't the model's to change.

One honest limit: the model writes the *why*, and prose can embellish. In one run it added that the kit would run out "before the inbound shipment arrives" — there is none. The numbers and the decisions can't move; the sentences around them deserve a quick read.

## Before you plan real stock with it

- **Connect the real data.** Replace `PRODUCTS`, `INBOUND` and `sales_history` with your WMS/ERP and your carriers' tracking APIs.
- **Use a better forecast if you have one.** `build_plan` takes any number per product; a seasonal model or your planning tool's forecast drops in where `forecast` is computed — still code, still reproducible.
- **Send the morning result somewhere.** `daily_check` stores it in memory; email the reorder list to purchasing or open purchase requisitions in your ERP.
- **Approve before ordering.** Turn "Order" into a draft purchase order and gate it with the [plan confirmation](../single-agent/09-plan-confirmation.md) building block, as in [Lead Qualification](03-lead-qualification.md).
- **Route optimization** is a solver's job, not a language model's: call an optimizer (OR-Tools, your TMS) from a step, and let the model explain its answer.

## Next

👉 Back to [Use Cases](index.md)
