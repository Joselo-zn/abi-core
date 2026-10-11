# Customer Support & Service Triage

A support bot has one job it must never get wrong: not making things up.

You've met the other kind. Ask it about instalments and it cheerfully invents a twelve-month plan your company has never offered. Ask for your order and it apologizes, beautifully, without ever looking the order up. Ask for a human and it asks you to rephrase. Then a person finally takes over and opens with "how can I help you today?" — and you explain everything again, from the top.

Here's the version I'd put in front of your customers. It answers from your help center and only from your help center. It looks orders up instead of guessing. When it doesn't know, it says so, in words you wrote, not words the model improvised. And when it hands you to a person, that person gets a three-line summary, so nobody starts from zero.

It takes about twenty minutes to build. Most of it is reading.

## What you'll build

One agent, `support`, that reads every message and decides what it's about:

```
message
  │
  ├─ a five-digit order number?  ──────── look the order up (code) → describe it (model)
  ├─ a help-center question?  ─── find the entry (code) → does it answer this? (model, yes/no)
  │                                   ├─ yes → answer from the entry (model)
  │                                   └─ no  → a fixed "I'd rather not guess" (code)
  ├─ wants a person?  ─────────────────── summarize the conversation (model) → open a ticket (code)
  └─ anything else  ───────────────────── a short, careful reply (model)
```

The model does what it's good at: understanding a message and writing a reply. The code does everything that has to be right every time: finding order numbers, choosing the help-center entry, refusing to guess, opening the ticket, remembering the conversation.

ABI features on this page: tasks and steps, an `@agent.tool`, [session memory](../single-agent/04-agents-with-memory.md), and status updates while the agent works.

## Step 1: Create the project and the agent

```bash
abi-core create project --name helpdesk
cd helpdesk
```

Answer `n` to the semantic layer and to Guardian — one agent doesn't need them — and press Enter for the rest. Then:

```bash
abi-core add agent --name support \
  --description "Answers customer questions, tracks orders and hands complex cases to a human" \
  --with-web-interface
```

When it asks for tasks/skills, type `support`. Press Enter for the URL.

## Step 2: The data

The help center and the orders. In production these are calls to your knowledge base and your order system; here they're two Python structures, so you can see every value the agent can ever quote.

Create `agents/support/data.py`:

```python
"""Sample data. In production these come from your help center and your order system."""

FAQ = [
    {
        "question": "What is your return policy?",
        "answer": "You can return any item within 30 days of delivery for a full refund, as long as it's unused and in its original packaging.",
        "keywords": ["return", "refund", "send back", "money back"],
    },
    {
        "question": "How long does shipping take?",
        "answer": "Standard shipping takes 3 to 5 business days. Express shipping takes 1 to 2 business days.",
        "keywords": ["shipping", "delivery time", "how long", "arrive", "express"],
    },
    {
        "question": "How do I change my shipping address?",
        "answer": "You can change the address from your account page until the order ships. After that, contact the carrier with your tracking number.",
        "keywords": ["address", "change address", "wrong address"],
    },
    {
        "question": "Which payment methods do you accept?",
        "answer": "We accept credit and debit cards, PayPal and bank transfer.",
        "keywords": ["pay", "payment", "card", "paypal", "transfer"],
    },
]

ORDERS = {
    "10045": {"status": "shipped", "carrier": "DHL", "tracking": "DHL-88231", "eta": "2026-10-14"},
    "10046": {"status": "processing", "carrier": None, "tracking": None, "eta": "2026-10-16"},
    "10047": {"status": "delivered", "carrier": "FedEx", "tracking": "FX-55120", "eta": "2026-10-08"},
}
```

## Step 3: The prompts

Six short prompts, each for one small job. Notice what they don't do: none of them asks the model to decide what happens next.

Create `agents/support/prompts.py`:

```python
CLASSIFY_PROMPT = """You route customer support messages.

Conversation so far:
{history}

New message: {message}

Reply with exactly one word:
- faq: a general question about policies, shipping, payments or accounts
- order_status: the customer asks about a specific order
- human: the customer asks for a person, is upset, or the problem is complex
- other: greetings, thanks, or anything else"""

FAQ_CHECK_PROMPT = """Does this help-center entry fully answer the customer's question?
Answer only yes or no.

Q: {question}
A: {answer}

Customer question: {message}"""

FAQ_PROMPT = """You are a friendly support agent. Answer the customer using ONLY this help-center entry.

Help-center entry:
Q: {question}
A: {answer}

Customer: {message}"""

ORDER_PROMPT = """You are a friendly support agent. Tell the customer the status of order {order_id}
in two sentences, using only these facts: {order}

Customer: {message}"""

CHAT_PROMPT = """You are a friendly support agent for an online store. Reply briefly.
Never state store policies, prices, dates or options you weren't given. If the customer
asks about one, say you don't have that information and offer to pass the question
to a colleague.

Conversation so far:
{history}

Customer: {message}"""

HANDOFF_PROMPT = """Summarize this support conversation for the human agent taking over.
Three short lines: what the customer wants, what has been tried, what is still open.

{history}"""
```

## Step 4: The order lookup tool

Replace the contents of `agents/support/tools.py`:

```python
from app import agent
from data import ORDERS


@agent.tool(name="get_order")
async def get_order(order_id: str):
    """Look up an order by its number. Replace ORDERS with a call to your order system."""
    order = ORDERS.get(order_id)
    return {"found": order is not None, "order_id": order_id, "order": order}
```

It's an `@agent.tool`, so the task can call it by name today — and if you later let the model call tools itself, it's already one.

## Step 5: The steps

Each step does one thing. Some ask the model, some don't, and the names tell you which.

Replace the contents of `agents/support/steps.py`:

```python
import re

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from data import FAQ
from prompts import CHAT_PROMPT, CLASSIFY_PROMPT, FAQ_CHECK_PROMPT, FAQ_PROMPT, HANDOFF_PROMPT, ORDER_PROMPT

INTENTS = {"faq", "order_status", "human", "other"}


@agent.step(name="classify")
async def classify(message, history):
    """Ask the model for the intent; code makes sure the answer is one we handle."""
    raw = await invoke(config.LLM_CONFIG, CLASSIFY_PROMPT.format(message=message, history=history))
    words = re.findall(r"[a-z_]+", raw.lower())
    intent = next((w for w in reversed(words) if w in INTENTS), "other")
    return {"intent": intent}


@agent.step(name="find_order_id")
async def find_order_id(message):
    """Order numbers are five digits. A regex finds them; no model needed."""
    match = re.search(r"\b\d{5}\b", message)
    return {"order_id": match.group(0) if match else None}


@agent.step(name="find_faq")
async def find_faq(message):
    """Pick the help-center entry whose keywords appear most in the message."""
    text = message.lower()
    scored = [(sum(k in text for k in entry["keywords"]), entry) for entry in FAQ]
    score, best = max(scored, key=lambda pair: pair[0])
    return {"faq": best if score > 0 else None}


@agent.step(name="faq_covers")
async def faq_covers(message, faq):
    """A yes/no question the model answers; the code decides what to do with it."""
    raw = await invoke(config.LLM_CONFIG, FAQ_CHECK_PROMPT.format(message=message, **faq))
    return {"covered": raw.strip().lower().startswith("yes")}


@agent.step(name="answer_faq")
async def answer_faq(message, faq):
    reply = await invoke(config.LLM_CONFIG, FAQ_PROMPT.format(message=message, **faq))
    return {"reply": reply}


@agent.step(name="answer_order")
async def answer_order(message, order_id, order):
    reply = await invoke(config.LLM_CONFIG, ORDER_PROMPT.format(message=message, order_id=order_id, order=order))
    return {"reply": reply}


@agent.step(name="chat")
async def chat(message, history):
    reply = await invoke(config.LLM_CONFIG, CHAT_PROMPT.format(message=message, history=history))
    return {"reply": reply}


@agent.step(name="summarize_for_human")
async def summarize_for_human(history):
    summary = await invoke(config.LLM_CONFIG, HANDOFF_PROMPT.format(history=history))
    return {"summary": summary}
```

Two things worth a second look. `classify` doesn't trust the model's word blindly: it keeps only an answer it knows how to handle, and falls back to `other`. And `faq_covers` asks the model a yes/no question instead of letting it decide what to say — the decision stays in the task.

## Step 6: The task

This is the skeleton — where every decision is made, in plain Python.

Replace the contents of `agents/support/tasks.py`:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse
from abi_core.common.utils import format_conversation_summary

TICKETS = []  # In production: create the ticket in your help-desk system instead.


@agent.task(name="support", task_id="task-support")
async def support(query, context_id=None):
    session = await agent.get_session_context(context_id)
    turns = session.get("conversation_summary") or []
    history = format_conversation_summary(turns) or "(new conversation)"

    # 1. Decide what the customer needs. The model proposes, the code decides.
    yield AgentResponse.status("Reading your message...")
    order_id = (await agent.execute_step("find_order_id", message=query))["order_id"]
    if order_id and session.get("awaiting_order_id"):
        intent = "order_status"  # they're answering our question
    else:
        intent = (await agent.execute_step("classify", message=query, history=history))["intent"]
        if order_id and intent != "human":
            intent = "order_status"  # an order number beats a guess
    awaiting_order_id = False

    # 2. Act on it.
    if intent == "faq":
        faq = (await agent.execute_step("find_faq", message=query))["faq"]
        covered = faq and (await agent.execute_step("faq_covers", message=query, faq=faq))["covered"]
        if covered:
            reply = (await agent.execute_step("answer_faq", message=query, faq=faq))["reply"]
        else:
            # Not in the help center: a fixed answer, so the model can't invent a policy.
            reply = ("I don't have that in our help center, and I'd rather not guess. "
                     "Want me to pass your question to a colleague?")

    if intent == "order_status":
        if not order_id:
            reply = "Happy to check. What's your order number? It has five digits."
            awaiting_order_id = True
        else:
            yield AgentResponse.status(f"Looking up order {order_id}...")
            found = await agent.execute_step("get_order", order_id=order_id)
            if found["found"]:
                reply = (await agent.execute_step(
                    "answer_order", message=query, order_id=order_id, order=found["order"]
                ))["reply"]
            else:
                reply = f"I can't find order {order_id}. Could you double-check the number?"
                awaiting_order_id = True

    if intent == "human":
        yield AgentResponse.status("Handing you over to a colleague...")
        full_history = format_conversation_summary(turns + [{"user": query, "assistant": ""}])
        summary = (await agent.execute_step("summarize_for_human", history=full_history))["summary"]
        ticket = {"id": f"TCK-{len(TICKETS) + 1:04d}", "context_id": context_id, "summary": summary}
        TICKETS.append(ticket)
        reply = (
            f"I've passed this to a colleague — your ticket is {ticket['id']}. "
            f"They'll see this summary, so you won't have to repeat yourself:\n\n{summary}"
        )

    if intent == "other":
        reply = (await agent.execute_step("chat", message=query, history=history))["reply"]

    # 3. Remember the turn, so the next message has the whole conversation.
    turns = (turns + [{"user": query, "assistant": reply}])[-10:]
    await agent.update_session_context(
        context_id, {"conversation_summary": turns, "awaiting_order_id": awaiting_order_id}
    )
    yield AgentResponse.text(reply)
```

## Step 7: Run it

qwen3 thinks out loud before it answers. That helps on hard problems and only slows down short replies like these, so turn it off for this agent. In `compose.yaml`, add one line to the `environment` of the `helpdesk-support` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Then pull the model and start everything:

```bash
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 8: Talk to it

Use [`AgentStreamClient`](../single-agent/05-testing-agents.md#talk-to-it-from-python): one client is one customer, so the whole conversation shares a session. Save this as `chat.py` in the project folder:

```python
import asyncio
from abi_core.client.agent_stream_client import AgentStreamClient

MESSAGES = [
    "Hi! How long does shipping usually take?",
    "Thanks!",
    "Where is my order?",
    "It's 10045",
    "Can I pay in instalments over 12 months?",
    "Do you ship to Canada?",
    "This is taking too long, I want to talk to a person.",
]


async def main():
    client = AgentStreamClient("http://localhost:8002")  # one client = one customer
    for message in MESSAGES:
        print(f"\n>>> {message}")
        async for event in client.stream(message):
            if event.get("is_task_completed"):
                print(event.get("content"))


asyncio.run(main())
```

```bash
python chat.py
```

Here's a real run, on a laptop CPU with `qwen3:latest`:

```
>>> Hi! How long does shipping usually take?
Hi! Standard shipping usually takes 3 to 5 business days. If you need it faster, express shipping is available and takes 1 to 2 business days.

>>> Thanks!
You're welcome! If you need any further assistance, feel free to ask. 😊

>>> Where is my order?
Happy to check. What's your order number? It has five digits.

>>> It's 10045
Your order 10045 has been shipped by DHL with tracking number DHL-88231. The estimated time of arrival is October 14, 2026.

>>> Can I pay in instalments over 12 months?
I don't have that in our help center, and I'd rather not guess. Want me to pass your question to a colleague?

>>> Do you ship to Canada?
I don't have that in our help center, and I'd rather not guess. Want me to pass your question to a colleague?

>>> This is taking too long, I want to talk to a person.
I've passed this to a colleague — your ticket is TCK-0001. They'll see this summary, so you won't have to repeat yourself:

**Customer wants:** To speak to a human agent due to unresolved questions.
**What's been tried:** Assistant provided shipping info and order status, but couldn't answer payment terms or shipping to Canada.
**Still open:** Customer is requesting to speak with a live agent immediately.
```

The whole conversation — seven messages — took about 70 seconds on a CPU, between 4 and 20 seconds per reply. On a GPU, or with a cloud model, it's close to instant. The wording changes from run to run; the decisions held steady in every run I tried.

You can also give it a proper chat window: `abi-core add chainlit`, then `abi-core run`.

## What happened

1. **"How long does shipping take?"** The model said `faq`. Code found the shipping entry by its keywords, the model confirmed the entry answers the question, and the reply was written from that entry alone.
2. **"Where is my order?"** No order number, so the code asked for one and remembered, in the session, that it was waiting for it.
3. **"It's 10045."** The code saw a five-digit number while waiting for one, skipped the classification, looked the order up, and the model turned the record into two sentences.
4. **"Can I pay in instalments?"** The payments entry matched by keyword, but the model answered *no* to "does this entry answer the question?". So the customer got the fixed sentence — not an invented policy.
5. **"I want to talk to a person."** The model said `human`. The code asked the model for a three-line summary of the whole conversation and opened a ticket with it.

What the model never did: pick an order number, choose a help-center entry, decide to refuse, decide to escalate on its own, or write down anything it would have to remember.

## Before you put it in front of customers

- **Plug in the real systems.** Replace `ORDERS` with your order API and `FAQ` with your help center — through the [Semantic Layer](../semantic-layer/04-extending-semantic-layer.md) if you want search by meaning instead of keywords.
- **Open real tickets.** `TICKETS` lives in memory and disappears on restart. Create the ticket in your help-desk tool instead, and pass the summary along.
- **Make sessions survive.** Set `SESSION_BACKEND=redis`, so conversations survive restarts and work across replicas — see [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md).
- **Add more channels.** Email, WhatsApp or a web widget each just call `/stream` with a session per customer.
- **Look for the gaps.** Every "I'd rather not guess" is a question your help center doesn't answer yet. Log them.

## Next

👉 Back to [Use Cases](index.md)
