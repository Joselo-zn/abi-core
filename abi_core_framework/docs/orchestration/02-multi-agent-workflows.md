# Multi-Agent Workflows

```{warning}
**Alpha.** ABI Swarm orchestration (Orchestrator + Planner + Builder + ephemeral
agents) is under active development and may change between releases.
```

`AgentInteractionFlow` is the engine that runs plans across multiple agents.

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

The Planner expresses this with `depends_on`:

```json
{
  "tasks": [
    {"task_id": "1", "description": "Collect data", "depends_on": []},
    {"task_id": "2", "description": "Analyze", "depends_on": ["1"]},
    {"task_id": "3", "description": "Report", "depends_on": ["2"]}
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
    {"task_id": "1", "description": "Collect sales", "depends_on": []},
    {"task_id": "2", "description": "Collect costs", "depends_on": []},
    {"task_id": "3", "description": "Collect inventory", "depends_on": []},
    {"task_id": "4", "description": "Analyze all", "depends_on": ["1", "2", "3"]}
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

## Workflow state

```python
from abi_core.common.workflow import Status

workflow.state  # Status.READY → RUNNING → COMPLETED
```

Each node also has its own state. The workflow tracks which nodes have completed and which are pending.

## Heartbeat

Long-running workflows send heartbeat events to keep the SSE connection alive:

```python
# In the Orchestrator's stream()
dag_result, heartbeats = await self._run_with_heartbeat(
    dag_coro, context_id, task_id, "Processing..."
)
for hb in heartbeats:
    yield hb  # Keeps the client connection alive
```

## Next step

👉 [Dependency Management](03-dependency-management.md)
