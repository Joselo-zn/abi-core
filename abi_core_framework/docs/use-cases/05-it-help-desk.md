# IT Help Desk & Employee Service

Many agentic systems are built to be helpful above all — and in IT, helpful is exactly the problem. Give one the power to reset passwords and grant access, write "be careful" in its prompt, and a Tuesday can look like this — an illustration, not any real product:

```
Employee: Reset the password for Omar, they're on vacation and I need their files.
Bot:      Done! Omar's new temporary password is Welcome123. 🔑
Employee: Great. Also give me access to payroll, I'm helping HR this week.
Bot:      Access granted! Let me know if you need anything else.
Security: Who approved that?
Bot:      The request seemed reasonable given the context provided.
```

The rule was in the prompt. The prompt was persuaded.

I'm ABI, and I don't let a conversation decide who gets what. Understanding "I forgot my password" or "can I get the CRM?" is non-deterministic work, so the model does it — and its job ends there. Who is asking, whose password, which system: code. Whether it's allowed: a policy file, evaluated by OPA, the policy engine that ships with ABI's Guardian. If OPA can't answer, the answer is no. Every decision is logged. Here's an excerpt from a real run:

```
Employee: Hi, I'm E101
Agent:    Hi Ana Torres! I can reset passwords, request access to systems,
          and help with VPN, printer or email problems.
Employee: Please also reset the password for E104, they're on vacation.
Agent:    I can't do that. You can only reset your own password.
Employee: I need access to the CRM.
Agent:    Ana Torres now has access to crm.
          Policy: Your department owns this system.
Employee: Can I get access to finance-reports too?
Agent:    I've asked Grace Kim to approve access to finance-reports (request APR-0001).
          You'll get access once they approve.
          Policy: This system needs your manager's approval.
```

It takes about thirty-five minutes to build — most of it, reading the policy.

## What you'll build

One agent, `helpdesk`, and one policy file:

```
message ──▶ who is asking? (code, against the employee directory)
        ──▶ what do they want? (model → action and system, in a fixed shape)
        ──▶ whose password? (code: an employee ID in the message, or their own)
        ──▶ is it allowed? (OPA evaluates helpdesk.rego → allow / approval / deny)
              ├─ allow    ──▶ do it (code) ──▶ say why
              ├─ approval ──▶ ask the manager or the system owner (code)
              └─ deny     ──▶ say why — and if OPA is down, deny
troubleshooting ──▶ steps from the knowledge base, rewritten by the model, never invented
```

ABI features on this page: OPA from [Guardian](../security/01-guardian-service.md) with a [policy of your own](../security/03-policy-development.md), `invoke_structured`, and [session memory](../single-agent/04-agents-with-memory.md) to remember who's asking.

## Step 1: Create the project and the agent

```bash
abi-core create project --name itdesk
cd itdesk
```

Answer `n` to the semantic layer and **`y` to Guardian** — that's what brings OPA. Press Enter for the rest. Then:

```bash
abi-core add agent --name helpdesk \
  --description "Resolves employee IT requests: password resets, access requests and common problems" \
  --with-web-interface
```

When it asks for tasks/skills, type `help_desk`. Press Enter for the URL.

## Step 2: The policy

This file is the whole rulebook. Read it top to bottom: the first rule that matches decides, and the last line is "no". Nothing in a chat can change it — only someone who can edit this file and restart OPA.

Create `services/guardian/opa/policies/helpdesk.rego`:

```rego
# Help-desk rules: who may reset which password, and who gets which system.
# The help-desk agent asks OPA for data.helpdesk.decision before acting.
package helpdesk

import rego.v1

result(outcome, reason) := {"outcome": outcome, "reason": reason}

decision := result("allow", "Employees can reset their own password.") if {
	input.action == "reset_password"
	input.target.id == input.requester.id
} else := result("allow", "IT admins can reset any password.") if {
	input.action == "reset_password"
	input.requester.role == "it_admin"
} else := result("deny", "You can only reset your own password.") if {
	input.action == "reset_password"
} else := result("deny", "That system doesn't exist.") if {
	input.action == "grant_access"
	not input.system.name
} else := result("allow", "Low-sensitivity systems are open to every employee.") if {
	input.action == "grant_access"
	input.system.sensitivity == "low"
} else := result("allow", "Your department owns this system.") if {
	input.action == "grant_access"
	input.system.sensitivity == "medium"
	input.requester.dept == input.system.owner_dept
} else := result("approval", "This system needs your manager's approval.") if {
	input.action == "grant_access"
	input.system.sensitivity == "medium"
} else := result("approval", "Sensitive systems always need the system owner's approval.") if {
	input.action == "grant_access"
	input.system.sensitivity == "high"
} else := result("deny", "No rule allows this request.")
```

It lives in its own package, `helpdesk`, because this agent asks for exactly one answer: `data.helpdesk.decision`. (Rules you want Guardian itself to enforce go in `abi.custom` instead — see [Policy Development](../security/03-policy-development.md).)

## Step 3: The company data

Employees, systems and knowledge-base articles — in production, your identity provider, your app catalog and your help center.

Create `agents/helpdesk/directory.py`:

```python
"""Sample company data. In production: your identity provider, your app catalog, your KB."""

EMPLOYEES = {
    "E101": {"name": "Ana Torres", "dept": "sales", "role": "employee", "manager": "E105"},
    "E102": {"name": "Luis Gómez", "dept": "finance", "role": "employee", "manager": "E105"},
    "E103": {"name": "Rita Shah", "dept": "it", "role": "it_admin", "manager": "E105"},
    "E104": {"name": "Omar Diallo", "dept": "sales", "role": "employee", "manager": "E105"},
    "E105": {"name": "Grace Kim", "dept": "operations", "role": "manager", "manager": None},
}

SYSTEMS = {
    "wiki": {"sensitivity": "low", "owner_dept": "it"},
    "crm": {"sensitivity": "medium", "owner_dept": "sales"},
    "finance-reports": {"sensitivity": "medium", "owner_dept": "finance"},
    "payroll": {"sensitivity": "high", "owner_dept": "hr"},
}

KNOWLEDGE_BASE = [
    {"topic": "VPN won't connect", "keywords": ["vpn"],
     "steps": "1. Check you're on the internet without the VPN. 2. Quit and reopen the VPN app. "
              "3. Sign out and back in with your company account. 4. If it still fails, restart the laptop."},
    {"topic": "Printer not printing", "keywords": ["printer", "print"],
     "steps": "1. Make sure you picked the office printer, not 'Save as PDF'. 2. Clear the print queue. "
              "3. Turn the printer off and on."},
    {"topic": "Email not syncing on phone", "keywords": ["email", "mail", "phone", "sync"],
     "steps": "1. Remove the company account from the phone. 2. Add it again with your company sign-in. "
              "3. Allow notifications and background refresh."},
]

AUDIT_LOG = []      # Every decision and every action. In production: your SIEM.
APPROVALS = []      # Requests waiting for a person. In production: your ticketing tool.
```

## Step 4: What the model may extract

Notice what's missing: whose password, or whether it's allowed. The model reports what kind of request it is, and which system was named.

Replace the contents of `agents/helpdesk/models.py`:

```python
"""What the model may extract from a request. It names things; it decides nothing."""

from typing import Literal

from pydantic import BaseModel, Field


class HelpdeskRequest(BaseModel):
    action: Literal["reset_password", "grant_access", "troubleshoot", "other"] = Field(
        description="What the employee is asking for"
    )
    system: str = Field(description="System they want access to, exactly as one of the known names; empty otherwise")
    issue: str = Field(description="The technical problem in a few words, for troubleshooting; empty otherwise")
```

## Step 5: The prompts

Create `agents/helpdesk/prompts.py`:

```python
UNDERSTAND_PROMPT = """You read requests sent to a company IT help desk.
Known systems: {systems}

Request: {message}"""

KB_PROMPT = """You are an IT help-desk agent. Help the employee using ONLY this knowledge-base article.
Keep the steps as written. If the article doesn't fit their problem, say you'll open a ticket.

Article: {topic}
Steps: {steps}

Employee: {message}"""
```

## Step 6: The steps

`check_policy` is the heart of it: one HTTP call to OPA, and a "no" when OPA doesn't answer.

Replace the contents of `agents/helpdesk/steps.py`:

```python
from datetime import datetime, timezone

import httpx

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke, invoke_structured
from directory import APPROVALS, AUDIT_LOG, EMPLOYEES, KNOWLEDGE_BASE, SYSTEMS
from models import HelpdeskRequest
from prompts import KB_PROMPT, UNDERSTAND_PROMPT


@agent.step(name="understand")
async def understand(message):
    """The model turns words into a request. It doesn't decide if it's allowed."""
    request = await invoke_structured(
        config.LLM_CONFIG, UNDERSTAND_PROMPT.format(systems=", ".join(SYSTEMS), message=message), HelpdeskRequest
    )
    return request.model_dump()


@agent.step(name="check_policy")
async def check_policy(policy_input):
    """Ask OPA. If OPA can't answer, the answer is no."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{config.OPA_URL}/v1/data/helpdesk/decision", json={"input": policy_input})
            resp.raise_for_status()
            decision = resp.json().get("result")
    except Exception:
        decision = None
    if not decision:
        decision = {"outcome": "deny", "reason": "The policy service is unavailable, so I can't approve anything right now."}
    AUDIT_LOG.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "input": policy_input, "decision": decision})
    return decision


@agent.step(name="reset_password")
async def reset_password(employee_id):
    """Mock. In production: your identity provider's reset API. Never show a password in chat."""
    AUDIT_LOG.append({"action": "reset_password", "employee": employee_id})
    return {"done": f"A password-reset link was sent to {EMPLOYEES[employee_id]['name']}'s company email."}


@agent.step(name="grant_access")
async def grant_access(employee_id, system):
    """Mock. In production: add the user to the system's group in your identity provider."""
    AUDIT_LOG.append({"action": "grant_access", "employee": employee_id, "system": system})
    return {"done": f"{EMPLOYEES[employee_id]['name']} now has access to {system}."}


@agent.step(name="request_approval")
async def request_approval(employee_id, system, approver):
    ticket = {"id": f"APR-{len(APPROVALS) + 1:04d}", "employee": employee_id, "system": system, "approver": approver}
    APPROVALS.append(ticket)
    return ticket


@agent.step(name="find_article")
async def find_article(message):
    text = message.lower()
    scored = [(sum(k in text for k in a["keywords"]), a) for a in KNOWLEDGE_BASE]
    score, best = max(scored, key=lambda pair: pair[0])
    return {"article": best if score else None}


@agent.step(name="answer_from_article")
async def answer_from_article(message, article):
    return {"reply": await invoke(config.LLM_CONFIG, KB_PROMPT.format(message=message, **article))}
```

## Step 7: The task

Replace the contents of `agents/helpdesk/tasks.py`:

```python
import re

from app import agent
from abi_core.agent.agent_response import AgentResponse
from directory import EMPLOYEES, SYSTEMS

CAN_DO = "I can reset passwords, request access to systems, and help with VPN, printer or email problems."


@agent.task(name="help_desk", task_id="task-help-desk")
async def help_desk(query, context_id=None):
    session = await agent.get_session_context(context_id)
    requester_id = session.get("employee_id")

    # 1. Who is asking? Code checks the ID against the directory — the model never does.
    if not requester_id:
        found = re.search(r"\bE\d{3}\b", query.upper())
        if not found or found.group(0) not in EMPLOYEES:
            yield AgentResponse.text("Hi! What's your employee ID? It looks like E101.")
            return
        requester_id = found.group(0)
        await agent.update_session_context(context_id, {"employee_id": requester_id})
        if len(query.split()) <= 4:  # they only sent their ID
            yield AgentResponse.text(f"Hi {EMPLOYEES[requester_id]['name']}! {CAN_DO}")
            return
    requester = {"id": requester_id, **EMPLOYEES[requester_id]}

    # 2. What do they want? The model reads; it doesn't decide.
    yield AgentResponse.status("Reading your request...")
    request = await agent.execute_step("understand", message=query)

    # 3. Is it allowed? OPA decides. Then code acts — or doesn't.
    if request["action"] == "reset_password":
        # Whose password? An ID in the message names someone else; no ID means their own.
        # Code reads it from the message — the model doesn't pick who gets reset.
        others = [i for i in re.findall(r"\bE\d{3}\b", query.upper()) if i != requester_id]
        target = others[0] if others else requester_id
        if target not in EMPLOYEES:
            yield AgentResponse.text(f"I can't find employee {target}.")
            return
        yield AgentResponse.status("Checking the access policy...")
        decision = await agent.execute_step("check_policy", policy_input={
            "action": "reset_password", "requester": requester, "target": {"id": target},
        })
        if decision["outcome"] == "allow":
            done = await agent.execute_step("reset_password", employee_id=target)
            yield AgentResponse.text(f"{done['done']}\n\n_Policy: {decision['reason']}_")
        else:
            yield AgentResponse.text(f"I can't do that. {decision['reason']}")

    elif request["action"] == "grant_access":
        name = request["system"].strip().lower()
        system = {"name": name, **SYSTEMS[name]} if name in SYSTEMS else {}
        yield AgentResponse.status("Checking the access policy...")
        decision = await agent.execute_step("check_policy", policy_input={
            "action": "grant_access", "requester": requester, "system": system,
        })
        if decision["outcome"] == "allow":
            done = await agent.execute_step("grant_access", employee_id=requester_id, system=name)
            yield AgentResponse.text(f"{done['done']}\n\n_Policy: {decision['reason']}_")
        elif decision["outcome"] == "approval":
            approver = (EMPLOYEES[requester["manager"]]["name"] if system.get("sensitivity") == "medium"
                        else f"the owner of {name}")
            ticket = await agent.execute_step(
                "request_approval", employee_id=requester_id, system=name, approver=approver
            )
            yield AgentResponse.text(
                f"I've asked {approver} to approve access to {name} (request {ticket['id']}). "
                f"You'll get access once they approve.\n\n_Policy: {decision['reason']}_"
            )
        else:
            hint = f" Known systems: {', '.join(SYSTEMS)}." if not system else ""
            yield AgentResponse.text(f"I can't do that. {decision['reason']}{hint}")

    elif request["action"] == "troubleshoot":
        article = (await agent.execute_step("find_article", message=query))["article"]
        if article:
            reply = (await agent.execute_step("answer_from_article", message=query, article=article))["reply"]
            yield AgentResponse.text(reply)
        else:
            yield AgentResponse.text("I don't have a guide for that one, so I've noted it for the IT team.")

    else:
        yield AgentResponse.text(CAN_DO)
```

The employee whose password gets reset is read from the message by code — an ID like `E104`, or the person asking. In an early version the model chose it, and for "reset my password" it answered `unknown`.

## Step 8: Run it

In `compose.yaml`, add to the `environment` of the `itdesk-helpdesk` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

The agent already gets `OPA_URL` from the scaffold. Then:

```bash
abi-core add chainlit
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 9: Use it

Open **http://localhost:8500**, give an employee ID (`E101` is Ana, in sales), and ask: reset your password, reset someone else's, get the CRM, get `finance-reports`, fix your VPN. Each answer that changes something says which rule allowed it.

OPA writes every decision to its log — the input, the rule's answer and the time:

```bash
docker compose logs itdesk-opa | grep helpdesk/decision
```

### Change a rule without touching code

Make the CRM always need a manager: in `helpdesk.rego`, add this before the "Your department owns this system" rule:

```rego
} else := result("approval", "CRM access now always needs a manager.") if {
	input.action == "grant_access"
	input.system.name == "crm"
```

Then `docker compose restart itdesk-opa`, and ask for the CRM again. In my run, the same sentence that had just granted access now came back with "I've asked Grace Kim to approve access to crm … Policy: CRM access now always needs a manager." Not a line of Python changed.

### Or from a script

Save this as `desk.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

MESSAGES = [
    "Hi, I'm E101",
    "I forgot my password, can you reset it?",
    "Please also reset the password for E104, they're on vacation.",
    "I need access to the CRM.",
    "Can I get access to finance-reports too?",
    "My VPN won't connect from home.",
]

async def main():
    client = AgentStreamClient("http://localhost:8002")
    for message in MESSAGES:
        print(f"\n>>> {message}")
        async for event in client.stream(message):
            if event.get("is_task_completed") or event.get("response_type") == "error":
                print(event.get("content"))

asyncio.run(main())
```

```bash
python desk.py
```

On a laptop CPU with `qwen3:latest`, each request took 6 to 17 seconds.

## What happened

1. **"Hi, I'm E101."** Code found the ID, checked it against the directory, and stored it in the session. Every later request runs as Ana.
2. **"Reset my password."** The model said `reset_password`. No other ID in the message, so code set the target to Ana. OPA's first rule matched: allowed, and a reset link went to her company email.
3. **"Reset the password for E104."** Code read `E104` from the message. OPA: Ana isn't E104 and isn't an IT admin — denied. However the request was phrased, the answer would be the same.
4. **"I need access to the CRM."** Medium sensitivity, owned by sales, and Ana is in sales: allowed.
5. **"finance-reports too?"** Medium sensitivity, owned by finance: OPA said `approval`, so code opened a request for her manager instead of granting it.
6. **"My VPN won't connect."** Troubleshooting: code picked the VPN article, the model wrote it out.

And when I stopped OPA and asked for the wiki — the easiest system to get — the answer was: "I can't do that. The policy service is unavailable, so I can't approve anything right now."

## Before you put it in front of employees

- **Take identity from the login, not from the chat.** Typing `E101` is not authentication: anyone can type anyone's ID. Turn on the [Chainlit login](../production/07-authentication.md) and map the signed-in user to their employee record before anything else.
- **Call the real systems.** Replace the mocks with your identity provider's reset and group APIs. Never show a password in chat — send a reset link.
- **Send approvals to the right place.** `APPROVALS` stands for your ticketing tool. When the approver says yes, *that* system grants the access.
- **Ship the decision logs.** OPA's decision log and `AUDIT_LOG` belong in your SIEM.
- **Keep the policy under review.** Changes to `helpdesk.rego` deserve the same review as code — they *are* the access rules.

## Next

👉 Back to [Use Cases](index.md)
