# Dependency Management

Manage dependencies between tasks in complex workflows.

## Dependencies

A task can depend on others:

```python
{
    "task_id": "generate_report",
    "dependencies": ["collect_data", "analyze_data"]
}
```

The Orchestrator executes tasks only when their dependencies are complete.

## Next Steps

- [Result synthesis](04-result-synthesis.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
