# Multi-Agent Workflows

Create complex workflows that coordinate multiple agents.

## Workflow Types

### Sequential
```
Agent 1 → Agent 2 → Agent 3
```

### Parallel
```
Agent 1 →
Agent 2 → Combine results
Agent 3 →
```

### Hybrid
```
Agent 1 → Agent 2 →
                    → Agent 4
Agent 3 ────────────→
```

## Workflow Example

```python
# Planner creates this plan
plan = {
    "tasks": [
        {"id": "task_1", "agent": "collector", "dependencies": []},
        {"id": "task_2", "agent": "analyst", "dependencies": ["task_1"]},
        {"id": "task_3", "agent": "reporter", "dependencies": ["task_2"]}
    ]
}

# Orchestrator executes it
```

## Next Steps

- [Dependency management](03-dependency-management.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
