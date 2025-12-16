# Planner and Orchestrator

The Planner and Orchestrator coordinate complex workflows with multiple agents.

## What They Do

### Planner
- Divides complex tasks into subtasks
- Finds appropriate agents
- Creates execution plan

### Orchestrator
- Executes the plan
- Coordinates agents
- Synthesizes results

## Add Orchestration Layer

```bash
abi-core add agentic-orchestration-layer
```

This creates:
- Planner Agent (port 11437)
- Orchestrator Agent (port 8002)

## Use the System

```bash
# Send complex query to Orchestrator
curl -X POST http://localhost:8083/stream \
  -d '{
    "query": "Analyze last month sales and generate report",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

The Orchestrator:
1. Sends query to Planner
2. Planner creates plan with subtasks
3. Orchestrator executes each subtask
4. Combines results

## Next Steps

- [Multi-agent workflows](02-multi-agent-workflows.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
