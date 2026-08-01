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

## Write the steps

Edit `agents/runner/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
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
async def execute_action(action):
    """Carry out a single planned action. This is where real work happens —
    call a tool, write a file, hit an API. Here we just ask the AI to do it."""
    result = await invoke(config.LLM_CONFIG, f"Do this: {action}\nReport what you did.")
    return {"action": action, "outcome": result}
```

## Write the task

The task is what turns a variable-length plan into a loop of step calls. Edit `agents/runner/tasks.py`:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="plan_and_execute", task_id="task-plan-exec")
async def plan_and_execute(query):
    """Plan the request, then execute every action the plan produced."""
    yield AgentResponse.status("Planning...")
    plan_result = await agent.execute_step("plan", query=query)
    actions = plan_result["actions"]

    outcomes = []
    for i, action in enumerate(actions, 1):
        yield AgentResponse.status(f"Step {i}/{len(actions)}: {action}")
        outcome = await agent.execute_step("execute_action", action=action)
        outcomes.append(outcome)

    yield AgentResponse.result({"actions": actions, "outcomes": outcomes})
```

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
3. The task looped over that list, calling `execute_action` once per item
4. Each `agent.execute_step(...)` call is a plain Python call inside the same process — no network hop, no other agent involved
5. Every outcome accumulated into one final response

## Key rules

- A **step** does one deterministic thing (call the AI, do the work). It never decides how many times it runs.
- A **task** is what decides that: it's ordinary Python, so it can loop, branch, or run steps in parallel with `asyncio.gather`.
- Because the plan's length comes from the AI at runtime, this can't be a fixed `@agent.step(depends_on=[...])` DAG (see [Dependency Management](../orchestration/03-dependency-management.md)) — a DAG's shape is fixed when the agent starts. A task is imperative code, so it can shape itself around whatever the AI just produced.
- This is still **one agent, one process**. If `execute_action` needs to become a specialized agent of its own — a research expert, a code writer, anything with its own tools and model — you're no longer looping in-process. See [Plan, Then Execute — Two Agents](../multi-agent-basics/05-plan-then-execute.md) for that split.

## Next step

👉 [Testing Agents](05-testing-agents.md)
