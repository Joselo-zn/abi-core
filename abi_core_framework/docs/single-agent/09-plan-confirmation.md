# Plan Confirmation — Let the User Approve Before You Act

```{note}
**Alpha.** The plan-confirmation API is under active development. It's the
same building block ABI Swarm's Orchestrator uses — extracted here so a
single agent gets it too, not just the swarm.
```

The agent from [Plan and Execute](08-plan-and-execute.md) plans, then runs — no pause in between. That's fine for "write a haiku." It's not fine for "delete these files" or "spend a large model on this." This page adds a checkpoint: the agent proposes a plan, the user approves, rejects, or asks for changes — *then* it runs.

## What you'll build

The same `runner` agent from the previous page, now:
1. Picking a decomposition methodology (WBS, SMART, GTD, Polya) before planning — the same technique the swarm's Planner uses
2. Showing the plan and waiting for a reply instead of executing immediately
3. Handling three replies: approve → run it, reject → cancel, request changes → re-plan with feedback

## Pick a methodology first

`select_methodology` asks the LLM which decomposition strategy fits the request, then hands that guidance to your prompt — same call the swarm's Planner makes, just importable directly:

```python
# agents/runner/steps.py
from abi_core.common.methodology_tools import select_methodology, list_methodologies

@agent.step(name="plan")
async def plan(query):
    methodology_result = await select_methodology(query, config.LLM_CONFIG)
    methodology_block = (
        f"\n\nMethodology to apply: {methodology_result['methodology']} — "
        f"{list_methodologies()[methodology_result['methodology']]}"
    )
    prompt = f"""Break this request into an ordered list of concrete actions.
Request: {query}{methodology_block}

Reply with ONLY this JSON, nothing else:
{{"actions": ["first action", "second action", ...]}}"""
    raw = await invoke(config.LLM_CONFIG, prompt)
    return {
        "actions": clean_llm_json(raw)["actions"],
        "methodology": methodology_result["methodology"],
        "methodology_rationale": methodology_result["rationale"],
    }
```

`select_methodology` is best-effort — an LLM hiccup or an unparseable reply just falls back to `WBS`, it never raises.

## Add the confirmation gate

This needs a real `context_id` to hang a pending plan off of — see [Sessions & Multi-turn](07-sessions-multi-turn.md) if you haven't already added sessions. The gate itself is three functions from `abi_core.agent.plan_confirmation`:

```python
# agents/runner/tasks.py
from abi_core.agent.agent_response import AgentResponse
from abi_core.agent.plan_confirmation import (
    classify_plan_confirmation_reply,
    record_pending_plan,
    clear_pending_plan,
)
from abi_core.common.utils import format_plan_summary


@agent.task(name="plan_and_execute", task_id="task-plan-and-execute")
async def plan_and_execute(query, context_id=None, task_id=None):
    session_context = await agent.get_session_context(context_id) if context_id else {}
    reply = classify_plan_confirmation_reply(query, session_context) if context_id else None

    plan_result = None
    if reply is not None:
        classification = reply["classification"]
        if classification == "plan_confirmed":
            plan_result = reply["pending_plan"]
            await clear_pending_plan(agent.update_session_context, context_id)
        elif classification == "plan_rejected":
            await clear_pending_plan(agent.update_session_context, context_id)
            yield AgentResponse.text("Plan cancelled.")
            return
        elif classification == "plan_modify_requested":
            await agent.update_session_context(context_id, {"awaiting_plan_modification": True})
            yield AgentResponse.input_required("What would you like to change about the plan?")
            return
        elif classification == "plan_modify_feedback":
            enriched = f"{reply['original_query']}\n\nRequested changes: {reply['feedback']}"
            async for r in _plan_then_confirm(enriched, context_id):
                yield r
            return
    else:
        async for r in _plan_then_confirm(query, context_id):
            yield r
        return

    # ── Plan approved — run it ──
    actions = plan_result["actions"]
    outcomes = []
    for i, action in enumerate(actions, 1):
        yield AgentResponse.status(f"Step {i}/{len(actions)}: {action}")
        outcome = await agent.execute_step("execute_action", action=action, context_id=context_id)
        outcomes.append(outcome)
    yield AgentResponse.result({"actions": actions, "outcomes": outcomes})


async def _plan_then_confirm(query, context_id):
    """First turn for this query: plan, then stop and ask — don't run yet."""
    yield AgentResponse.status("Planning...")
    plan_result = await agent.execute_step("plan", query=query)

    if not context_id:
        # No session, nowhere to park a pending plan — fall back to running
        # immediately (same behavior as before this page).
        actions = plan_result["actions"]
        outcomes = [await agent.execute_step("execute_action", action=a, context_id=context_id) for a in actions]
        yield AgentResponse.result({"actions": actions, "outcomes": outcomes})
        return

    await record_pending_plan(agent.update_session_context, context_id, plan_result, query)
    display_plan = {
        "objective": query,
        "methodology": plan_result.get("methodology"),
        "methodology_rationale": plan_result.get("methodology_rationale"),
        "tasks": [
            {"task_id": f"action_{i}", "description": a}
            for i, a in enumerate(plan_result["actions"], 1)
        ],
    }
    yield AgentResponse.input_required(format_plan_summary(display_plan), action_type="plan_confirmation")
```

`classify_plan_confirmation_reply(query, session_context)` does the actual reading of minds — given the incoming message and whatever's in session context, it tells you which of four things just happened, or `None` if this is a brand-new request:

| Classification | Meaning |
|---|---|
| `plan_confirmed` | User approved — `reply["pending_plan"]` has the stored plan |
| `plan_rejected` | User said no |
| `plan_modify_requested` | User wants changes, hasn't said what yet |
| `plan_modify_feedback` | User just described the changes — `reply["feedback"]` |

It matches natural language ("sí", "yes", "no", "cancelar", "aprobar") as well as fixed sentinel strings a UI's approve/reject/modify buttons can send — `PLAN_CONFIRM_APPROVE`, `PLAN_CONFIRM_REJECT`, `PLAN_CONFIRM_MODIFY` (also importable from `abi_core.agent.plan_confirmation`).

## Talk to it

Confirmation needs a session that survives across two separate requests — start one first:

```bash
TOKEN=$(curl -s -X POST http://localhost:8002/session/start -d '{}' | jq -r .session_token)
```

**Turn 1 — ask, get a plan back:**

```bash
curl -N -X POST http://localhost:8002/stream \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Write a haiku about the moon, then translate it to Italian"}'
```

```
event: input_required
data: 📋 Plan Created
      🎯 Objective: Write a haiku about the moon, then translate it to Italian
      🧭 Methodology: SMART — ...
      Tasks (2):
        1. action_1: Write a haiku about the moon
        2. action_2: Translate the written haiku to Italian
      Reply to approve, reject, or request changes.
```

**Turn 2 — approve, with the same token:**

```bash
curl -N -X POST http://localhost:8002/stream \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "sí"}'
```

```
event: status → "Step 1/2: Write a haiku about the moon"
event: status → "Step 2/2: Translate the written haiku to Italian"
event: result → {"actions": [...], "outcomes": [...]}
```

Reply `"no"` instead and you'll get `"Plan cancelled."` with nothing executed. Reply with the modify sentinel (or "cambiar"-style phrasing your own triage recognizes) and you'll be asked what to change, then re-planned with your feedback folded in.

## What happened

1. `select_methodology` picked a decomposition strategy before the actual planning call — same technique, same registry, the swarm's Planner uses
2. The first turn planned, then stopped — `record_pending_plan` parked the plan in session context and the task yielded `input_required` instead of running anything
3. The second turn's query ("sí") had no pending-plan-shaped content of its own — `classify_plan_confirmation_reply` recognized it as a reply *to* the pending plan, using the session context from turn 1
4. Because the session token resolves to the same `context_id` on both requests, the plan recorded in turn 1 was still there in turn 2
5. Only after classification came back `plan_confirmed` did the task actually loop over `execute_action`

## Key rules

- **This needs a real session.** Without a `context_id` that persists across requests, there's nowhere to remember "there's a plan waiting for a reply" — see [Sessions & Multi-turn](07-sessions-multi-turn.md).
- **`classify_plan_confirmation_reply` is a pure function.** No I/O, no LLM call — it's a deterministic read of `query` + whatever's in session context. Cheap to call on every turn.
- **Don't forget `awaiting_plan_modification`.** It's what tells the *next* turn "the next thing you get is feedback, not a new request" — skip setting it and a modify request silently loses the plan it was supposed to change.
- **This is the same primitive the swarm uses.** ABI Swarm's Orchestrator calls the exact same `classify_plan_confirmation_reply`/`record_pending_plan`/`clear_pending_plan` — what differs is what happens *after* approval: the swarm hands off to the Builder over A2A, a single agent just loops over its own steps.

## Next step

👉 [Testing Agents](05-testing-agents.md)
