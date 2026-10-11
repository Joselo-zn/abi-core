# Dependency Management

How ABI-Core handles execution order — both within a single agent and across multiple agents.

## Inside one agent

Steps registered with `@agent.step(depends_on=[...])` compile into a `ToolExecutionGraph`. Nodes at the same level run in parallel. The graph enforces order.

```python
# These two run in parallel (no dependency between them)
@agent.step(name="classify_query")
async def classify_query(query): ...

@agent.step(name="guardian_validate")
async def guardian_validate(query): ...

# This waits for both to finish
@agent.step(
    name="gate_decision",
    depends_on=["classify_query", "guardian_validate"],
    input_map={
        "classification": "$classify_query.classification",
        "guardian_result": "$guardian_validate",
    }
)
async def gate_decision(classification, guardian_result): ...
```

### input_map references

Use `$node_name.key` to wire outputs between steps:

| Reference | Meaning |
|-----------|---------|
| `$input.query` | The original input to the DAG |
| `$classify_query.classification` | The `classification` key from classify_query's return dict |
| `$guardian_validate` | The entire return dict from guardian_validate |

## Across multiple agents

The Planner produces tasks with `dependencies` arrays. The Orchestrator respects them:

```json
{
  "tasks": [
    {"task_id": "task_1", "description": "Get data", "dependencies": []},
    {"task_id": "task_2", "description": "Analyze", "dependencies": ["task_1"]},
    {"task_id": "task_3", "description": "Visualize", "dependencies": ["task_1"]},
    {"task_id": "task_4", "description": "Report", "dependencies": ["task_2", "task_3"]}
  ]
}
```

Execution:
1. Task 1 runs first (no deps)
2. Tasks 2 and 3 run in parallel (both depend only on 1)
3. Task 4 waits for both 2 and 3

### Waiting for several dependencies

If you build a workflow yourself, pass all of a node's dependencies to `add_edge` **in one call**:

```python
# analyze, visualize and report are InteractionFlowNode objects already added with add_node()
workflow.add_edge([analyze.id, visualize.id], report.id)   # report runs once, after both
```

Edges use each node's `id`. Calling `add_edge(analyze.id, report.id)` and then `add_edge(visualize.id, report.id)` creates two independent triggers: `report` would run twice, each time as soon as one of its dependencies finished. One call with the full list creates a real "wait for all" join.

### What a dependent task receives

In ABI Swarm, a task that depends on others starts with their output already in its workspace — the actual files, downloaded from the [Artifact Store](../production/05-artifact-store.md) — plus a description of what those files expose, so it uses them instead of rewriting them.

That handover goes through the shared session store. Set `SESSION_BACKEND=redis` and `SESSION_REDIS_URL` on the Orchestrator **and on the Builder**: the Builder passes them on to every agent it creates. Without them, each new agent falls back to its own in-memory store and works blind to the others — see [Environment Variables](../reference/environment-variables.md#session-management).

## Programmatic parallelism in tasks

Inside a `@agent.task`, use `asyncio.gather` for explicit parallel execution:

```python
import asyncio

@agent.task(name="parallel_work", task_id="task-parallel")
async def parallel_work(query):
    # Run two steps at the same time
    result_a, result_b = await asyncio.gather(
        agent.execute_step("step_a", text=query),
        agent.execute_step("step_b", text=query),
    )
    yield AgentResponse.result({"a": result_a, "b": result_b})
```

## Next step

👉 [Result Synthesis](04-result-synthesis.md)
