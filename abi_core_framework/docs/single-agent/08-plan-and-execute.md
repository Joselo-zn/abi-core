# Plan and Execute — One Agent, Many Actions

Fixed pipelines like the chatbot's `classify → respond` only work when you know in advance how many steps a request needs. Real requests vary — "say hi" is one action, "write a haiku and translate it" is two. This page builds an agent that asks the AI to plan a variable-length list of actions, then executes each one — no separate planner agent, no network hop, all inside one process.

## What you'll build

An agent that:
1. Turns a request into an ordered list of actions (the "plan")
2. Executes each action in turn, one at a time
3. Returns every outcome together

## Create the agent

```bash
abi-core add agent runner \
  --description "Plans and executes multi-step requests" \
  --with-web-interface
```

Tasks/skills when prompted:
```
plan_and_execute
```

Each `execute_action` call below is otherwise stateless — without shared memory, a later step (like "translate the haiku") has no way to see what an earlier step (like "write the haiku") produced. Add the [built-in memory API](06-builtin-memory.md) so steps can pass context to each other:

```bash
abi-core add service agent-memory
```

This adds the Agent Memory Server + Redis to `compose.yaml` and wires `AGENT_MEMORY_URL` into `runner` automatically (retroactively, since the agent already exists).

## Write the steps

Edit `agents/runner/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from abi_core.agent import add_short_term_memory, get_short_term_memory
from abi_core.common.utils import clean_llm_json


@agent.step(name="plan")
async def plan(query):
    """Ask the AI to break the request into an ordered list of actions."""
    prompt = f"""Break this request into an ordered list of concrete actions.
Request: {query}

Reply with ONLY this JSON, nothing else:
{{"actions": ["first action", "second action", ...]}}"""
    raw = await invoke(config.LLM_CONFIG, prompt)
    return {"actions": clean_llm_json(raw)["actions"]}


@agent.step(name="execute_action")
async def execute_action(action, context_id):
    """Carry out a single planned action. This is where real work happens —
    call a tool, write a file, hit an API. Here we just ask the AI to do it.

    Reads prior steps' outcomes from short-term memory so, e.g., a
    "translate the haiku" action can see the haiku a previous action wrote —
    then writes its own outcome back for the steps after it."""
    history = await get_short_term_memory(context_id=context_id)
    prompt = f"{history}\n\nDo this: {action}\nReport what you did." if history else f"Do this: {action}\nReport what you did."
    result = await invoke(config.LLM_CONFIG, prompt)
    await add_short_term_memory(
        "plan_and_execute", action, f"Action: {action}\nOutcome: {result}", context_id=context_id
    )
    return {"action": action, "outcome": result}
```

## Write the task

The task is what turns a variable-length plan into a loop of step calls. Edit `agents/runner/tasks.py`:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="plan_and_execute", task_id="task-plan-exec")
async def plan_and_execute(query, context_id=None):
    """Plan the request, then execute every action the plan produced."""
    yield AgentResponse.status("Planning...")
    plan_result = await agent.execute_step("plan", query=query)
    actions = plan_result["actions"]

    outcomes = []
    for i, action in enumerate(actions, 1):
        yield AgentResponse.status(f"Step {i}/{len(actions)}: {action}")
        outcome = await agent.execute_step("execute_action", action=action, context_id=context_id)
        outcomes.append(outcome)

    yield AgentResponse.result({"actions": actions, "outcomes": outcomes})
```

The framework injects `context_id` into the task automatically (one per conversation/session) — declaring it in the signature is enough to receive it, and passing it on to `execute_action` is what lets memory tie every action in the same request together.

## Run it

```bash
docker compose up --build -d
```

## Talk to it

```bash
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a haiku about the ocean, then translate it to Spanish"}'
```

You'll see something like:
```
event: status → "Planning..."
event: status → "Step 1/2: Write a haiku about the ocean"
event: status → "Step 2/2: Translate the haiku to Spanish"
event: result → {"actions": [...], "outcomes": [...]}
```

## What happened

1. The task called the `plan` step, which asked the AI for a JSON list of actions
2. The number of actions wasn't fixed anywhere in the code — the AI decided there were two
3. The task looped over that list, calling `execute_action` once per item, passing along the shared `context_id`
4. Each `agent.execute_step(...)` call is a plain Python call inside the same process — no network hop, no other agent involved
5. Before doing its work, each `execute_action` call read prior outcomes from short-term memory (via `context_id`), so "translate the haiku" actually saw the haiku "write a haiku" produced — then wrote its own outcome back for whatever runs next
6. Every outcome accumulated into one final response

Without memory, each `execute_action` call is stateless — step 2 has no way to know what step 1 did. That's the bug this page's `agent-memory` service fixes: the same `context_id` ties every action in one request together.

## Key rules

- A **step** does one deterministic thing (call the AI, do the work). It never decides how many times it runs.
- A **task** is what decides that: it's ordinary Python, so it can loop, branch, or run steps in parallel with `asyncio.gather`.
- Because the plan's length comes from the AI at runtime, this can't be a fixed `@agent.step(depends_on=[...])` DAG (see [Dependency Management](../orchestration/03-dependency-management.md)) — a DAG's shape is fixed when the agent starts. A task is imperative code, so it can shape itself around whatever the AI just produced.
- Steps don't share state on their own — if a later action needs to see what an earlier one produced, thread it through explicitly, e.g. with the [built-in memory API](06-builtin-memory.md) keyed by `context_id`, as done here.
- This is still **one agent, one process**. If `execute_action` needs to become a specialized agent of its own — a research expert, a code writer, anything with its own tools and model — you're no longer looping in-process. See [Plan, Then Execute — Two Agents](../multi-agent-basics/05-plan-then-execute.md) for that split.

## Next step

👉 [Plan Confirmation](09-plan-confirmation.md) — let the user approve the plan before this agent runs it.
