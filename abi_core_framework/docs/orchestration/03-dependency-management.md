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

The Planner produces tasks with `depends_on` arrays. The Orchestrator respects them:

```json
{
  "tasks": [
    {"task_id": "1", "description": "Get data", "depends_on": []},
    {"task_id": "2", "description": "Analyze", "depends_on": ["1"]},
    {"task_id": "3", "description": "Visualize", "depends_on": ["1"]},
    {"task_id": "4", "description": "Report", "depends_on": ["2", "3"]}
  ]
}
```

Execution:
1. Task 1 runs first (no deps)
2. Tasks 2 and 3 run in parallel (both depend only on 1)
3. Task 4 waits for both 2 and 3

### How a multi-dependency wait is actually built

Task 4 above has two dependencies (`"2"` and `"3"`), and it must run exactly once, only after both finish — not once per dependency. `build_workflow` (`orchestrator/agent/steps.py`) builds this by collecting *all* of a task's dependency ids first and calling `AgentInteractionFlow.add_edge` **once**, passing the full list (`add_edge(["2", "3"], "4")`), instead of once per dependency. This matters because of how the underlying `StateGraph.add_edge` (LangGraph) works: it only creates a real "wait for all" join when every predecessor is passed together in one call. Calling `add_edge` once per dependency — even targeting the same node — registers each call as its own independent trigger, so the target would fire once per call instead of once after all predecessors complete. This was a real, reproduced bug (a task with 3 dependencies ran 3 times, one with 4 ran 4 times, each firing as soon as its first dependency alone finished) and is now fixed: `add_edge` accepts `str | list[str]`, and every caller with more than one dependency for the same target must group them into a single call. See `AgentInteractionFlow.add_edge`'s docstring in `abi_core/common/workflow.py` for the full detail.

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
