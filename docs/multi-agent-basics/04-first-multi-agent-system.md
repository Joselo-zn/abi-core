# Your First Multi-Agent System

Create a complete system with multiple agents working together.

## What You'll Build

An analysis system with 3 agents:
1. **Collector**: Gets data
2. **Analyst**: Analyzes data
3. **Reporter**: Generates reports

## Step 1: Create the Project

```bash
abi-core create project analysis-system --with-semantic-layer
cd analysis-system
abi-core provision-models
```

## Step 2: Create the Agents

```bash
# Agent 1: Collector
abi-core add agent collector \
  --description "Collects data from sources"

# Agent 2: Analyst
abi-core add agent analyst \
  --description "Analyzes collected data"

# Agent 3: Reporter
abi-core add agent reporter \
  --description "Generates reports"
```

## Step 3: Create Agent Cards

```bash
abi-core add agent-card collector \
  --url "http://collector-agent:8000" \
  --tasks "collect_data,get_sources"

abi-core add agent-card analyst \
  --url "http://analyst-agent:8001" \
  --tasks "analyze_data,calculate_metrics"

abi-core add agent-card reporter \
  --url "http://reporter-agent:8002" \
  --tasks "generate_report,format_data"
```

## Step 4: Start the System

```bash
docker-compose up -d
```

## Step 5: Test the System

```python
import requests

# Call collector
data = requests.post(
    "http://localhost:8000/stream",
    json={"query": "Collect sales data", "context_id": "test", "task_id": "1"}
).json()

# Call analyst
analysis = requests.post(
    "http://localhost:8001/stream",
    json={"query": f"Analyze: {data['content']}", "context_id": "test", "task_id": "2"}
).json()

# Call reporter
report = requests.post(
    "http://localhost:8002/stream",
    json={"query": f"Generate report from: {analysis['content']}", "context_id": "test", "task_id": "3"}
).json()

print(report['content'])
```

## Next Steps

- [Semantic layer](../semantic-layer/01-what-is-semantic-layer.md)
- [Advanced orchestration](../orchestration/01-planner-orchestrator.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
