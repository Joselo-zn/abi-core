# Multi-Agent Workflows

```{warning}
**Alpha.** ABI Swarm orchestration (Orchestrator + Planner + Builder + ephemeral
agents) is under active development and may change between releases.
```

`AgentInteractionFlow` is the engine that runs plans across multiple agents.

In the Orchestrator, this is what `build_workflow` constructs from the Planner's
plan — and it only runs *after* the user approves the plan (see
[Plan Confirmation](01-planner-orchestrator.md#plan-confirmation)), since building
the workflow is also what invokes the Builder to create ephemeral agents.

## What it does

Takes a plan (list of tasks with assigned agents) and runs them in the right order. Each task calls an agent and collects its response.

## Creating a workflow

```python
from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode
from config import AGENT_CARD

# Create the flow
workflow = AgentInteractionFlow()

# Add a node (one task = one agent call)
node = InteractionFlowNode(
    task="Analyze Q4 revenue data",
    source_agent_card=AGENT_CARD,
    target_agent_card=analyst_card,  # AgentCard from discovery
    node_key="analyze",
    node_label="Revenue Analysis",
)
workflow.add_node(node)
workflow.set_source_card(AGENT_CARD)

# Execute and stream results
async for chunk in workflow.run_workflow():
    print(chunk)  # A2A response chunks from the target agent
```

## Execution patterns

### Sequential

Tasks run one after another. Each depends on the previous.

```
collect_data → analyze_data → write_report
```

The Planner expresses this with `dependencies`:

```json
{
  "tasks": [
    {"task_id": "task_1", "description": "Collect data", "dependencies": []},
    {"task_id": "task_2", "description": "Analyze", "dependencies": ["task_1"]},
    {"task_id": "task_3", "description": "Report", "dependencies": ["task_2"]}
  ]
}
```

### Parallel

Tasks with no dependencies between them run at the same time.

```
collect_sales ──┐
collect_costs ──┼→ analyze_all
collect_inventory─┘
```

```json
{
  "tasks": [
    {"task_id": "task_1", "description": "Collect sales", "dependencies": []},
    {"task_id": "task_2", "description": "Collect costs", "dependencies": []},
    {"task_id": "task_3", "description": "Collect inventory", "dependencies": []},
    {"task_id": "task_4", "description": "Analyze all", "dependencies": ["task_1", "task_2", "task_3"]}
  ]
}
```

### Hybrid

Mix of sequential and parallel.

```
classify ──→ analyze ──┐
guardian ──────────────┼→ synthesize
                       │
search_context ────────┘
```

## What ABI Swarm adds on top

The reference agents use this engine to run whole plans, and they add a few guarantees you get without writing them yourself:

- **Each task builds on the real output of the ones before it.** Files produced by a task travel through the [Artifact Store](../production/05-artifact-store.md) to the tasks that depend on it — no task reimplements what an earlier one already wrote.
- **Every agent knows where it stands.** An agent created for one task also sees the plan's objective and the tasks around it, not just its own sentence.
- **The result is checked as a whole before you get it.** When a plan delivers several code files, the set is reviewed and run in the [code execution sandbox](../production/08-sandbox.md). Problems are repaired where possible, and anything still broken is reported to you word for word — a summary never presents a broken deliverable as working.
- **One failing agent doesn't sink the run.** If an agent fails, the work continues with what arrived, and the final answer says exactly what was missing.
- **Runs stay apart.** The [A2A policy](../security/06-a2a-validation.md) lets the agents created for one run talk to each other, and never to the agents of another run.

None of this needs agents to chat with each other. They coordinate through artifacts and checks that code performs — bounded in time, bounded in cost, and auditable after the fact.

## Workflow state

```python
from abi_core.common.workflow import Status

workflow.state  # Status.READY → RUNNING → COMPLETED
```

Each node also has its own state. The workflow tracks which nodes have completed and which are pending.

## Heartbeat

Long-running workflows send heartbeat events to keep the SSE connection alive.
`_run_with_heartbeat` is an async generator — it yields each heartbeat live,
the instant it occurs, then a final `_HeartbeatDone` wrapping the
coroutine's result:

```python
# In the Orchestrator's stream()
from abi_core.agent.agent import _HeartbeatDone

dag_result = None
async for item in self._run_with_heartbeat(dag_coro, context_id, task_id, "Processing..."):
    if isinstance(item, _HeartbeatDone):
        dag_result = item.value
    else:
        yield item  # Forwarded immediately — keeps the client connection alive
```

`max_wait` defaults to `None` (no external cap) — the coroutine is expected
to bound its own real work internally (a DAG step's own `timeout=`, an LLM
call's own per-call bound). Pass `max_wait` explicitly only for a coroutine
you know isn't bounded internally yet, as a temporary safety net.

### Progress from tasks running in other agents

Each agent wraps its own work in `_run_with_heartbeat`, so an ephemeral agent
running a plan task emits a heartbeat every ~15s while it works. For that to
reach the user, every hop has to forward it as it happens:

- **`AgentInteractionFlow.run_workflow()`** runs the plan as a LangGraph graph
  with `stream_mode=["custom", "updates"]`. Each node writes every event it
  receives from its agent through LangGraph's stream writer
  (`get_stream_writer()`), tagged with its node id, so events leave the graph
  the moment they arrive. `"updates"` is used only to detect pause/completion.
  Without the `"custom"` stream, a node only surfaced its events after the
  whole task finished — a 15-minute task looked silent for 15 minutes.
- **The Orchestrator** relays each event's text to its own client, whether the
  agent sent it as message text or as status text (heartbeats arrive as
  `status_update` events, parsed into `A2AResponse.status_message`).

`workflow.current_node_key` / `current_agent_name` are set per event, so with
several tasks running in parallel each event is attributed to the task that
actually produced it.

## Next step

👉 [Dependency Management](03-dependency-management.md)
