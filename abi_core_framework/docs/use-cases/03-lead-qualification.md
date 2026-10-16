# Intelligent Lead Qualification & Scoring

Many agentic systems are built to sound confident about everything — including which of your leads matter and what to promise them. Put one in front of your inbound pipeline and a Monday morning can look like this — an illustration, not any real product:

```
Rep:  Who should I call first?
Bot:  Sam Lee! Very high intent — 94/100. 🔥
Rep:  The student who asked for thesis resources?
Bot:  Great catch! Re-scoring... Sam Lee: 31/100.
Rep:  Why was it 94?
Bot:  Based on overall engagement signals and fit.
Rep:  And what did you send BrightFreight?
Bot:  A warm intro offering 20% off the annual plan and a demo Thursday at 10 AM!
```

A score nobody can explain. A discount nobody approved. A meeting nobody booked.

I'm ABI, and I split this job down the middle. Reading a messy email — "we have budget approved, could we see a demo next week?" — is non-deterministic work, so the model does it, and only reports what the message says. Everything that decides something is code: the score is plain rules with every point written down, the drafts may only use facts you gave them, anything that looks like a price or a time gets flagged, and nothing is sent until a person says so. Here's an excerpt from a real run:

```
Score  Tier     Lead           Why
  100  hot      Dana Ortiz     +25 420 employees; +15 decision maker (VP of Operations);
                               +15 visited pricing; +20 asked for a demo; +15 budget mentioned;
                               +10 buying this quarter
   55  warm     Priya Nair     +25 2300 employees; +15 decision maker (Head of IT); +15 visited pricing
   30  nurture  Marco Bianchi  +15 decision maker (Founder); +15 visited pricing
    0  nurture  Sam Lee        -20 personal email address

To Dana Ortiz (BrightFreight):
  Hi Dana, thanks for reaching out! We'd love to help automate your dispatch team. Our platform
  automates repetitive back-office work like dispatching and ticket routing. It connects to your
  existing email, spreadsheets, and CRM, and deploys in your own cloud or servers. Let's schedule
  a live demo at your convenience. — The Sales Team

Send these, reject them, or tell me what to change.
```

It takes about thirty minutes to build.

## What you'll build

One agent, `qualifier`, that scores every lead and drafts a first email for the hot ones:

```
each lead ──▶ enrich the company (tool)          ─┐
          ──▶ read the email → signals (model)    ├─▶ score with rules (code) ──▶ ranking table
          ──▶ pages visited, title, domain (data) ─┘

hot leads ──▶ draft an email from approved product facts (model)
          ──▶ flag prices, percentages, clock times (code)
          ──▶ a person approves / changes / rejects ──▶ only then: send

every hour ──▶ the same scoring, on its own — it never sends anything
```

ABI features on this page: `invoke_structured` (the model reports facts in a fixed shape), an `@agent.tool`, a ranking rendered as a [table](../single-agent/10-rich-elements.md) in the chat, the [plan confirmation](../single-agent/09-plan-confirmation.md) building block as a send gate, and [`@agent.task_schedule`](../production/06-background-and-scheduled-tasks.md) for the hourly re-scoring.

## Step 1: Create the project and the agent

```bash
abi-core create project --name sales
cd sales
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name qualifier \
  --description "Scores inbound leads, enriches them and drafts first outreach for a person to approve" \
  --with-web-interface
```

When it asks for tasks/skills, type `qualify`. Press Enter for the URL.

The hourly job needs the scheduler. Add this line to `agents/qualifier/requirements.txt`:

```
abi-core-ai[scheduler]
```

## Step 2: The data

Leads as they'd arrive from your website, inbox and CRM; what an enrichment provider would say about each company; and the product facts your sales team is allowed to claim.

Create `agents/qualifier/data.py`:

```python
"""Sample signals. In production: your web analytics, your inbox and your CRM."""

LEADS = [
    {
        "id": "L-101", "name": "Dana Ortiz", "title": "VP of Operations", "domain": "brightfreight.io",
        "pages_visited": ["pricing", "case-studies", "pricing"], "source": "contact form",
        "email": "Hi — we're evaluating tools to automate our dispatch team this quarter. "
                 "We have budget approved. Could we see a demo next week?",
    },
    {
        "id": "L-102", "name": "Sam Lee", "title": "Student", "domain": "gmail.com",
        "pages_visited": ["blog"], "source": "newsletter",
        "email": "Love the blog! Doing a thesis on AI agents, any resources?",
    },
    {
        "id": "L-103", "name": "Priya Nair", "title": "Head of IT", "domain": "northwind-health.com",
        "pages_visited": ["security", "pricing"], "source": "contact form",
        "email": "We need something for our help desk, probably next year. "
                 "What are your security certifications?",
    },
    {
        "id": "L-104", "name": "Marco Bianchi", "title": "Founder", "domain": "tinyshop.it",
        "pages_visited": ["pricing"], "source": "chat",
        "email": "How much does it cost for a 3-person shop?",
    },
]

# What an enrichment provider would return for each company domain.
COMPANIES = {
    "brightfreight.io": {"company": "BrightFreight", "industry": "logistics", "employees": 420},
    "northwind-health.com": {"company": "Northwind Health", "industry": "healthcare", "employees": 2300},
    "tinyshop.it": {"company": "TinyShop", "industry": "retail", "employees": 3},
}

# The only things the drafts may say about the product. In production: your approved messaging.
PRODUCT_FACTS = [
    "automates repetitive back-office work such as dispatching, ticket routing and data entry",
    "connects to the email, spreadsheets and CRM a team already uses",
    "deploys in the customer's own cloud or on their own servers",
    "a live demo with our team is available on request",
]

OUTBOX = []  # Emails "sent" by this demo. In production: your email or CRM sequence tool.
```

## Step 3: What the model may report

The model reads each email and fills this — four facts, no opinions, no score. The schema is enforced while it generates.

Replace the contents of `agents/qualifier/models.py`:

```python
"""What the model may read out of a lead's message. Facts only — no scores."""

from typing import List, Literal

from pydantic import BaseModel, Field


class EmailSignals(BaseModel):
    asks_for_demo: bool = Field(description="The lead asks for a demo, a call or a meeting")
    mentions_budget: bool = Field(description="The lead says budget exists or is approved")
    timeline: Literal["now", "this_quarter", "later", "unknown"] = Field(
        description="When they intend to buy, as stated"
    )
    needs: List[str] = Field(description="What they want to solve, in a few words each")
```

## Step 4: The prompts

Create `agents/qualifier/prompts.py`:

```python
SIGNALS_PROMPT = """Read this message from a potential customer and report what it says.
Only report what is written; if something isn't said, use false, "unknown" or an empty list.

Message:
{email}"""

OUTREACH_PROMPT = """Write a short first reply (under 90 words) from our sales team to this lead.
Answer what they asked, mention one product fact that matches their needs, and propose a next step.
Use ONLY these product facts — nothing else about the product:
{facts}
Don't invent prices, times, dates or customer names. Sign it "— The Sales Team".

Lead: {name}, {title} at {company}
Their message: {email}
{feedback}"""
```

## Step 5: The enrichment tool

Replace the contents of `agents/qualifier/tools.py`:

```python
from app import agent
from data import COMPANIES


@agent.tool(name="enrich_company")
async def enrich_company(domain: str):
    """Company facts for an email domain. Replace COMPANIES with your enrichment provider."""
    return COMPANIES.get(domain, {"company": domain, "industry": "unknown", "employees": None})
```

## Step 6: The steps

Read this file top to bottom and you know exactly how a lead gets its score. That's the point.

Replace the contents of `agents/qualifier/steps.py`:

```python
import re

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke, invoke_structured
from data import PRODUCT_FACTS
from models import EmailSignals
from prompts import OUTREACH_PROMPT, SIGNALS_PROMPT

FREE_EMAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}
SENIOR = ("vp", "head", "director", "chief", "founder", "owner")


@agent.step(name="read_signals")
async def read_signals(email):
    """The model reads the message. It reports facts; it doesn't score."""
    signals = await invoke_structured(config.LLM_CONFIG, SIGNALS_PROMPT.format(email=email), EmailSignals)
    return {"signals": signals.model_dump()}


@agent.step(name="score_lead")
async def score_lead(lead, company, signals):
    """Plain rules, every point explained. Change the numbers, not the model."""
    points = []
    employees = company.get("employees") or 0
    if lead["domain"] in FREE_EMAIL:
        points.append((-20, "personal email address"))
    elif employees >= 50:
        points.append((25, f"{employees} employees"))
    elif employees >= 10:
        points.append((10, f"{employees} employees"))
    if any(word in lead["title"].lower() for word in SENIOR):
        points.append((15, f"decision maker ({lead['title']})"))
    if "pricing" in lead["pages_visited"]:
        points.append((15, "visited pricing"))
    if signals["asks_for_demo"]:
        points.append((20, "asked for a demo"))
    if signals["mentions_budget"]:
        points.append((15, "budget mentioned"))
    timeline_points = {"now": 15, "this_quarter": 10}.get(signals["timeline"], 0)
    if timeline_points:
        points.append((timeline_points, f"buying {signals['timeline'].replace('_', ' ')}"))

    score = max(0, min(100, sum(p for p, _ in points)))
    tier = "hot" if score >= 70 else "warm" if score >= 40 else "nurture"
    return {"score": score, "tier": tier, "reasons": [f"{p:+d} {why}" for p, why in points]}


@agent.step(name="draft_outreach")
async def draft_outreach(lead, company, feedback=""):
    prompt = OUTREACH_PROMPT.format(
        name=lead["name"], title=lead["title"], company=company["company"], email=lead["email"],
        facts="\n".join(f"- {f}" for f in PRODUCT_FACTS),
        feedback=f"\nThe sales lead reviewing this asked: {feedback}" if feedback else "",
    )
    return {"draft": await invoke(config.LLM_CONFIG, prompt)}


@agent.step(name="check_draft")
async def check_draft(draft):
    """Prices, percentages and clock times are never ours to invent — flag any the model wrote."""
    found = re.findall(
        r"[$€£]\s?\d[\d,.]*|\d+\s?%|\d+\s?(?:per|/)\s?(?:month|year|user)|\b\d{1,2}(?::\d{2})?\s?[ap]\.?m\.?\b",
        draft, re.I,
    )
    return {"warnings": [f"mentions {f!r} — check it before sending" for f in found]}
```

Want different weights? Change the numbers in `score_lead`. The model isn't involved, so the same lead always gets the same score, and every point has a reason a sales rep can read.

## Step 7: The task and the hourly job

Replace the contents of `agents/qualifier/tasks.py`:

```python
import os
from datetime import datetime, timezone

from app import agent
from config import config
from abi_core.agent.agent_response import AgentResponse
from abi_core.agent.plan_confirmation import (
    classify_plan_confirmation_reply,
    clear_pending_plan,
    record_pending_plan,
)
from data import LEADS, OUTBOX

LAST_RUN = {}  # The scheduled job's latest results.


async def score_all():
    """Enrich, read and score every lead. Same steps for the chat and the schedule."""
    results = []
    for lead in LEADS:
        company = await agent.execute_step("enrich_company", domain=lead["domain"])
        signals = (await agent.execute_step("read_signals", email=lead["email"]))["signals"]
        scored = await agent.execute_step("score_lead", lead=lead, company=company, signals=signals)
        results.append({"lead": lead, "company": company, **scored})
    return sorted(results, key=lambda r: r["score"], reverse=True)


@agent.task(name="qualify", task_id="task-qualify")
async def qualify(query, context_id=None):
    session = await agent.get_session_context(context_id)
    pending = session.get("pending_plan")  # drafts waiting for approval, if any

    reply = await classify_plan_confirmation_reply(query, session, config.LLM_CONFIG, session_id=context_id)
    decision = reply["classification"] if reply else "new_request"

    if decision == "new_request":
        yield AgentResponse.status("Scoring leads...")
        results = await score_all()
        yield AgentResponse.element("dataframe", {"data": [
            {"Lead": r["lead"]["name"], "Company": r["company"]["company"], "Score": r["score"],
             "Tier": r["tier"], "Why": "; ".join(r["reasons"])}
            for r in results
        ]}, name="Lead ranking")
        hot = [r for r in results if r["tier"] == "hot"]
        if not hot:
            yield AgentResponse.text("No hot leads right now — nothing to send.")
            return
        async for response in _propose(hot, context_id):
            yield response

    elif decision == "plan_confirmed":
        for item in pending["drafts"]:
            OUTBOX.append({"to": item["lead"]["name"], "body": item["draft"]})
        await clear_pending_plan(agent.update_session_context, context_id)
        yield AgentResponse.text(f"Sent {len(pending['drafts'])} email(s). (In this demo they go to OUTBOX.)")

    elif decision == "plan_rejected":
        await clear_pending_plan(agent.update_session_context, context_id)
        yield AgentResponse.text("Nothing was sent.")

    elif decision == "plan_modify_requested":
        await agent.update_session_context(context_id, {"awaiting_plan_modification": True})
        yield AgentResponse.input_required("What should change in the emails?")

    elif decision == "plan_modify_feedback":
        yield AgentResponse.status("Rewriting the drafts...")
        async for response in _propose(pending["drafts"], context_id, feedback=reply["feedback"]):
            yield response

    else:
        yield AgentResponse.text("There are no drafts waiting. Ask me to score the leads.")


async def _propose(items, context_id, feedback=""):
    """Draft (or redraft) an email per hot lead, check it, and wait for approval."""
    drafts, blocks = [], []
    for item in items:
        draft = (await agent.execute_step(
            "draft_outreach", lead=item["lead"], company=item["company"], feedback=feedback
        ))["draft"]
        warnings = (await agent.execute_step("check_draft", draft=draft))["warnings"]
        drafts.append({"lead": item["lead"], "company": item["company"], "draft": draft})
        note = "".join(f"\n⚠️ {w}" for w in warnings)
        blocks.append(f"**To {item['lead']['name']} ({item['company']['company']}):**\n\n{draft}{note}")
    await record_pending_plan(agent.update_session_context, context_id, {"drafts": drafts}, "outreach")
    yield AgentResponse.input_required(
        "\n\n---\n\n".join(blocks) + "\n\n---\nSend these, reject them, or tell me what to change.",
        action_type="plan_confirmation",
    )


@agent.task_schedule(
    name="rescore_leads",
    trigger="interval",
    trigger_args={"minutes": int(os.getenv("RESCORE_MINUTES", "60"))},
)
async def rescore_leads():
    """Runs on its own, every hour by default. Scores only — it never sends anything."""
    results = await score_all()
    LAST_RUN.update({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hot": [r["lead"]["id"] for r in results if r["tier"] == "hot"],
    })
    return LAST_RUN
```

`rescore_leads` runs on its own: no request, no user. It reuses `score_all`, so the chat and the schedule can never disagree about a score — and it has no way to send anything.

## Step 8: Run it

In `compose.yaml`, add to the `environment` of the `sales-qualifier` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

`RESCORE_MINUTES` sets how often the job runs (60 by default). Then:

```bash
abi-core add chainlit
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 9: Use it

Open **http://localhost:8500** and write "Score the new leads." The ranking appears as a table, followed by the draft for each hot lead and the approve/modify/reject buttons. Ask for a change in plain words — "make it shorter and offer a demo slot this Thursday" — and the drafts come back rewritten and checked again.

Every hour the agent re-scores on its own; you'll see `rescore_leads` in its logs. Without Guardian, each run logs a warning that no policy was checked and goes ahead; with `--with-guardian`, OPA approves each run first — see [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md).

### Or from a script

Save this as `leads.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

MESSAGES = [
    "Score the new leads.",
    "Make it shorter and offer a demo slot this Thursday.",
    "Looks good, send it.",
]

async def main():
    client = AgentStreamClient("http://localhost:8002")
    for message in MESSAGES:
        print(f"\n>>> {message}")
        async for event in client.stream(message):
            if event.get("response_type") == "element":
                for row in event["content"]["props"]["data"]:
                    print(f"  {row['Score']:>3}  {row['Tier']:<8} {row['Lead']:<14} {row['Why']}")
            elif event.get("is_task_completed") or event.get("require_user_input") or event.get("response_type") == "error":
                print(event.get("content"))

asyncio.run(main())
```

```bash
python leads.py
```

On a laptop CPU with `qwen3:latest`, scoring the four leads and drafting the email took 30 to 45 seconds, the rewrite about 12, and the approval two.

## What happened

1. **"Score the new leads."** For each lead the tool looked up the company and the model read the email into `EmailSignals`. `score_lead` added up the points — Dana Ortiz got 100, and every one of those points is listed in the table.
2. **Only Dana was hot,** so only Dana got a draft. The model wrote it from `PRODUCT_FACTS`; `check_draft` found no price, percentage or time to flag. The drafts were parked in the session and shown with the buttons.
3. **"Make it shorter and offer a demo slot this Thursday."** Recognized as a change request. The drafts were rewritten with that instruction and checked again. "Thursday" is in the email because a person asked for it.
4. **"Looks good, send it."** Recognized as an approval. The emails went to `OUTBOX` — the only path there is.

What the model never did: score a lead, pick who gets an email, or send one.

One honest limit: code can flag a price or a time, but it can't tell whether a sentence about your product is true. That's why the drafts only see `PRODUCT_FACTS` — and why a person approves every email. Before grounding the drafts in those facts, one of my runs promised a "real-time tracking" feature nobody had mentioned.

## Before you point it at real leads

- **Connect the real sources.** Replace `LEADS` with your web analytics, form submissions and inbox, and `COMPANIES` with your enrichment provider.
- **Write scores back.** Push `score`, `tier` and the reasons to your CRM, so reps see why a lead is hot.
- **Send through your tools.** Replace `OUTBOX` with your email or sequence tool, and keep the approval step.
- **Keep `PRODUCT_FACTS` owned by marketing.** It's the whole vocabulary the drafts may use.
- **Store the hourly results.** `LAST_RUN` lives in memory; keep the scores in your CRM or a database, and set `ASYNC_TASK_BACKEND=redis` if you run more than one replica.
- **Mind the rules.** Contacting people is regulated (for example GDPR or CAN-SPAM): record consent and offer an opt-out.

## Next

👉 Back to [Use Cases](index.md)
