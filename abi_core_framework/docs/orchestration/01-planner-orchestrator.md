# Planner & Orchestrator

```{warning}
**Alpha.** The reference Orchestrator, Planner and Builder agents (the pieces behind ABI Swarm) are
under active development. Behavior may change between releases. Not recommended for production yet.
```

Hand a big request to a single model and it does what models do: it improvises a plan in its head and starts acting on it before anyone has seen it.

I split that job in three. The Orchestrator is the entry point: it checks the request and decides whether it needs a plan. The Planner breaks it into smaller tasks and finds an agent for each. The Builder creates the agents that don't exist yet. Together they turn one sentence into coordinated multi-agent work — and nothing runs until you say yes.

## How they work together

```
User request
  → Orchestrator
    ├─ Is it allowed? (Guardian)  ┐ in parallel
    ├─ Is it simple or complex?   ┘
    ├─ Decide: answer directly | ask the Planner | block
    ├─ Planner: break it into tasks, find an agent for each
    ├─ Show the plan to the user — wait for approve / reject / modify
    └─ Once approved: create missing agents → run the tasks → combine the results
  → Response to user
```

## The Orchestrator

The Orchestrator is an ordinary ABI agent. Its first moves are a DAG of `@agent.step` functions: a security check and a triage run **in parallel**, and a deterministic gate waits for both before anything else happens.

```python
@agent.step(name="classify_query", input_map={"query": "$input.query"})
async def classify_query(query):
    # Simple question, or does it need a plan?
    ...
    return {"classification": "complex"}


@agent.step(name="guardian_validate", input_map={"query": "$input.query"})
async def guardian_validate(query):
    # Ask Guardian whether this request is allowed
    ...
    return {"status": "approved", "allowed": True}


@agent.step(
    name="gate_decision",
    depends_on=["classify_query", "guardian_validate"],
    input_map={"triage": "$classify_query", "guardian": "$guardian_validate"},
)
def gate_decision(triage, guardian):
    if guardian.get("status") == "blocked":
        return {"action": "blocked"}
    if triage.get("classification") == "simple":
        return {"action": "respond_direct"}
    return {"action": "call_planner"}
```

`depends_on` sets the order; `input_map` wires each dependency's output (`$classify_query`) into a parameter.

The gate is plain Python. The model helps classify; your code decides. A blocked request never reaches the Planner, and a request never runs without passing Guardian.

The gate also recognizes two kinds of replies without asking a model: an answer to a pending clarification question, and an approve/reject/modify reply to a plan that is waiting for confirmation.

## The Planner

The Planner receives the request and returns a structured plan — an objective and a list of tasks, each with a description, the agent that should do it, and the tasks it depends on:

```json
{
  "status": "ready",
  "plan": {
    "objective": "Analyze Q4 sales and generate a report",
    "tasks": [
      {
        "task_id": "task_1",
        "description": "Analyze Q4 revenue data",
        "agents": [{"name": "analyst"}],
        "dependencies": []
      },
      {
        "task_id": "task_2",
        "description": "Write the report from the analysis",
        "agents": [],
        "dependencies": ["task_1"]
      }
    ]
  }
}
```

- **Agents are found by meaning.** For each task the Planner asks the [Semantic Layer](../semantic-layer/01-what-is-semantic-layer.md) who can do it. A task with no matching agent is marked to be built on demand.
- **Dependencies set the order.** Tasks that don't depend on each other run in parallel — see [Dependency Management](03-dependency-management.md).
- **It asks when it doesn't know.** If the request is ambiguous, the Planner returns `{"status": "needs_clarification", ...}` instead of guessing, and the Orchestrator forwards the questions to the user.
- **It remembers what worked.** Before planning, the Planner recalls similar past plans from long-term memory. When a plan finishes, its outcome is stored there. Next time, a similar request starts from experience instead of from zero.

### Fixed-format deliverables

Some deliverables don't need a new agent at all — "these contents, as a PDF" is a rendering job, not a reasoning job. For those, a task can name a fixed tool instead of an agent. Today that tool is `write_pdf` (`abi_core.common.library_tools`). It's a whitelist checked in code: the model can pick the tool for a task, but it can't run anything outside the list.

## Plan confirmation

The Orchestrator never executes a plan the moment it's produced. The system proposes; the user disposes.

1. The plan is shown as a readable summary: the objective, each step, and — for steps that need a new agent — whether its model is already installed or will be downloaded first.
2. The plan is parked in the session, so it survives the pause, even across replicas with the Redis session backend.
3. The Orchestrator stops and waits. In the Chainlit UI the plan appears as a review card with Approve / Modify / Reject.

On the next turn:

- **Approve** — only now are agents created and tasks run.
- **Reject** — the plan is dropped and nothing runs.
- **Modify** — the user's feedback goes back to the Planner, which produces a new plan that pauses for confirmation again.

If the pending plan expired before the reply arrived, the Orchestrator says so instead of running something the user no longer sees.

The same building block is available to any single agent — see [Plan Confirmation](../single-agent/09-plan-confirmation.md).

### Model availability

`abi_core.common.model_tools` maps every model to the Ollama host that has it, across one or more hosts:

```python
from abi_core.common.model_tools import list_available_models, find_model, pull_model

registry = await list_available_models()    # {"qwen3:latest": "http://ollama:11434", ...}
location = await find_model("qwen3:latest")  # host url, or None
await pull_model("qwen3:latest")             # download it if it's missing
```

The Orchestrator uses `find_model` read-only, to tell the user in the plan summary what will be downloaded. The Builder uses `pull_model` so a new agent is never started with a model that isn't there. Both are ordinary functions — wrap them in an `@agent.tool` in your own agents.

## Get orchestration in your project

There's no single CLI command that scaffolds the full Orchestrator + Planner + Builder bundle — that combined system is ABI Swarm, a separate product built on this framework.

The reference agents ship in `abi_agents` (`abi_agents.orchestrator`, `abi_agents.planner`, `abi_agents.builder`). To use the pattern in your own project, start from `abi-core create project --name my-app --with-semantic-layer --with-guardian` and wire each agent by hand: its source, its agent card, its registration in the Semantic Layer, and its service in `compose.yaml`.

## Next step

👉 [Multi-Agent Workflows](02-multi-agent-workflows.md)
