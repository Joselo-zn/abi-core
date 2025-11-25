# Multi-Agent Workflows

## Overview

ABI-Core provides a complete system for orchestrating complex multi-agent workflows. This guide explains how to design, implement, and execute workflows that coordinate multiple specialized agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                     Planner Agent                           │
│  • Decomposes query into tasks                             │
│  • Finds agents using semantic search                      │
│  • Creates execution plan with dependencies                │
│  • Handles clarification questions                         │
└────────────────────────┬────────────────────────────────────┘
                         │ Execution Plan (JSON)
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Agent                        │
│  • Validates agent availability                            │
│  • Executes workflow with LangGraph                        │
│  • Monitors progress and health                            │
│  • Synthesizes results                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Agent 1 │    │ Agent 2 │    │ Agent 3 │
    │Observer │    │ Actor   │    │Verifier │
    └─────────┘    └─────────┘    └─────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ↓
                  Synthesized Result
```

## Workflow Phases

### Phase 1: Task Decomposition

The Planner Agent receives a user query and:

1. **Analyzes the query** using Chain of Thought reasoning
2. **Identifies subtasks** that need to be performed
3. **Determines if clarification is needed**
4. **Finds appropriate agents** using semantic search
5. **Creates execution plan** with task dependencies

#### Example: Simple Query

**Input:**
```json
{
  "query": "Analyze sales data and generate report",
  "context_id": "session-001",
  "task_id": "task-001"
}
```

**Planner Output:**
```json
{
  "status": "ready",
  "plan": {
    "objective": "Analyze sales data and generate report",
    "tasks": [
      {
        "task_id": "task_1",
        "description": "Collect and analyze sales data",
        "agents": [
          {
            "name": "analyzer_agent",
            "id": "agent://analyzer_agent",
            "url": "http://analyzer:8000"
          }
        ],
        "dependencies": []
      },
      {
        "task_id": "task_2",
        "description": "Generate formatted report",
        "agents": [
          {
            "name": "reporter_agent",
            "id": "agent://reporter_agent",
            "url": "http://reporter:8001"
          }
        ],
        "dependencies": ["task_1"]
      }
    ],
    "execution_strategy": "sequential"
  }
}
```

#### Example: Query Needing Clarification

**Input:**
```json
{
  "query": "Analyze data",
  "context_id": "session-002",
  "task_id": "task-002"
}
```

**Planner Output:**
```json
{
  "status": "needs_clarification",
  "questions": [
    {
      "id": "q1",
      "question": "What type of data should I analyze?",
      "type": "required",
      "options": ["sales", "customer", "inventory", "financial"]
    },
    {
      "id": "q2",
      "question": "What time period?",
      "type": "required",
      "options": ["last 7 days", "last 30 days", "last quarter", "custom"]
    }
  ],
  "partial_understanding": "User wants data analysis but specifics unclear"
}
```

**User Provides Answers:**
```json
{
  "answers": {
    "q1": "sales",
    "q2": "last 30 days"
  }
}
```

**Planner Creates Plan** with clarified requirements.

### Phase 2: Agent Discovery

The Planner uses semantic search to find agents:

#### Semantic Tools

```python
# Find single best agent
agent = await tool_find_agent("analyze customer behavior patterns")
# Returns: {"name": "behavior_analyzer", "url": "http://...", ...}

# Get multiple recommendations
agents = await tool_recommend_agents(
    "process financial transactions",
    max_agents=3
)
# Returns: Top 3 agents ranked by semantic similarity
```

#### Matching Algorithm

The semantic layer matches tasks to agents using:

1. **Task Description Similarity**: Vector similarity between task and agent's `supportedTasks`
2. **Skill Matching**: Matching against skill descriptions and tags
3. **Capability Verification**: Ensuring agent has required capabilities
4. **Availability**: Checking agent health status

### Phase 3: Workflow Execution

The Orchestrator Agent receives the plan and:

1. **Validates agent availability** with health checks
2. **Creates workflow graph** from plan
3. **Executes tasks** according to dependencies
4. **Monitors progress** and streams updates
5. **Collects results** from each agent
6. **Synthesizes final output** using LLM

#### Health Checks

Before execution, Orchestrator checks each agent:

```python
for agent in plan.agents:
    health = await tool_check_agent_health(agent.name)
    
    if health['status'] != 'healthy':
        # Retry with exponential backoff
        # Attempts: 1s, 2s, 4s, 8s, 16s
        for attempt in range(5):
            await asyncio.sleep(2 ** attempt)
            health = await tool_check_agent_health(agent.name)
            if health['status'] == 'healthy':
                break
```

**If agents unavailable:**
```json
{
  "status": "on_hold",
  "unavailable_agents": [
    {
      "agent": "analyzer_agent",
      "retries": 5,
      "last_status": "unreachable",
      "last_error": "Connection timeout"
    }
  ],
  "message": "Workflow on hold until agents become available"
}
```

#### Workflow Graph

Orchestrator creates a LangGraph state machine:

```python
from langgraph.graph import StateGraph

# Create graph
workflow = StateGraph(WorkflowState)

# Add nodes for each task
for task in plan.tasks:
    workflow.add_node(task.task_id, create_task_node(task))

# Add edges for dependencies
for task in plan.tasks:
    for dep in task.dependencies:
        workflow.add_edge(dep, task.task_id)

# Compile and execute
app = workflow.compile()
result = await app.ainvoke(initial_state)
```

#### Progress Streaming

Orchestrator streams progress every 5 seconds:

```json
{
  "type": "progress",
  "timestamp": "2025-01-15T10:30:15Z",
  "completed_tasks": ["task_1"],
  "active_tasks": ["task_2"],
  "pending_tasks": ["task_3"],
  "progress_percentage": 33
}
```

### Phase 4: Result Synthesis

Orchestrator synthesizes results using LLM:

```python
prompt = f"""
Synthesize the following multi-agent workflow results:

Plan: {json.dumps(plan)}
Results: {json.dumps(results)}

Provide a coherent summary that:
1. Explains what was accomplished
2. Highlights key findings
3. Presents actionable insights
4. Hides implementation details
"""

synthesis = await llm.ainvoke([HumanMessage(content=prompt)])
```

**Output Format:**
```markdown
## Workflow Summary

### Objective
Analyze sales data and generate report

### Execution
- Analyzer Agent: Processed 10,000 sales records
- Reporter Agent: Generated comprehensive report

### Key Findings
- Sales increased 15% over last 30 days
- Top product category: Electronics (35% of revenue)
- Peak sales day: Friday

### Recommendations
1. Increase inventory for electronics
2. Focus marketing on Friday promotions
3. Expand product line in top categories

### Report
[Full report available at: /reports/sales-2025-01.pdf]
```

## Execution Strategies

### Sequential Execution

Tasks run one after another:

```json
{
  "execution_strategy": "sequential",
  "tasks": [
    {"task_id": "task_1", "dependencies": []},
    {"task_id": "task_2", "dependencies": ["task_1"]},
    {"task_id": "task_3", "dependencies": ["task_2"]}
  ]
}
```

**Timeline:**
```
task_1 ──→ task_2 ──→ task_3
```

### Parallel Execution

Independent tasks run concurrently:

```json
{
  "execution_strategy": "parallel",
  "tasks": [
    {"task_id": "task_1", "dependencies": []},
    {"task_id": "task_2", "dependencies": []},
    {"task_id": "task_3", "dependencies": []}
  ]
}
```

**Timeline:**
```
task_1 ──→
task_2 ──→
task_3 ──→
```

### Hybrid Execution

Mix of sequential and parallel:

```json
{
  "execution_strategy": "hybrid",
  "tasks": [
    {"task_id": "task_1", "dependencies": []},
    {"task_id": "task_2", "dependencies": []},
    {"task_id": "task_3", "dependencies": ["task_1", "task_2"]},
    {"task_id": "task_4", "dependencies": ["task_3"]}
  ]
}
```

**Timeline:**
```
task_1 ──→ ┐
           ├──→ task_3 ──→ task_4
task_2 ──→ ┘
```

## Complete Example

### Setup

```bash
# Create project
abi-core create project workflow-demo \
  --with-semantic-layer \
  --with-guardian

cd workflow-demo

# Add orchestration layer
abi-core add agentic-orchestration-layer

# Add worker agents
abi-core add agent data-collector \
  --description "Collects data from sources"

abi-core add agent data-analyzer \
  --description "Analyzes collected data"

abi-core add agent report-generator \
  --description "Generates formatted reports"

# Register agents
abi-core add agent-card data-collector \
  --url "http://data-collector:8000" \
  --tasks "collect_data,fetch_sources,aggregate_data"

abi-core add agent-card data-analyzer \
  --url "http://data-analyzer:8001" \
  --tasks "analyze_data,find_patterns,calculate_statistics"

abi-core add agent-card report-generator \
  --url "http://report-generator:8002" \
  --tasks "generate_report,format_output,create_visualizations"

# Provision models
abi-core provision-models

# Start system
abi-core run
```

### Execute Workflow

```python
import httpx
import json

async def execute_workflow():
    # Step 1: Send query to Orchestrator
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8083/stream",
            json={
                "query": "Collect sales data, analyze trends, and generate report",
                "context_id": "demo-001",
                "task_id": "workflow-001"
            },
            timeout=300.0
        )
        
        # Stream results
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                
                if data.get("type") == "progress":
                    print(f"Progress: {data['progress_percentage']}%")
                
                elif data.get("type") == "result":
                    print(f"Result: {data['content']}")
                
                elif data.get("type") == "error":
                    print(f"Error: {data['message']}")

# Run
import asyncio
asyncio.run(execute_workflow())
```

### Expected Output

```
Progress: 0%
Progress: 33%
Progress: 66%
Progress: 100%
Result: 
## Workflow Summary

### Objective
Collect sales data, analyze trends, and generate report

### Execution
- Data Collector: Retrieved 15,000 records from 3 sources
- Data Analyzer: Identified 5 key trends and patterns
- Report Generator: Created comprehensive PDF report

### Key Findings
- Overall sales growth: 18% YoY
- Seasonal pattern detected: Q4 peak
- Customer retention improved: 12%

### Recommendations
1. Increase Q4 inventory by 20%
2. Launch retention program in Q1
3. Expand top-performing product lines

### Report
Full report available at: /reports/sales-analysis-2025-01.pdf
```

## Error Handling

### Agent Unavailable

```python
try:
    result = await execute_workflow(plan)
except AgentUnavailableError as e:
    # Retry with backoff
    await asyncio.sleep(30)
    result = await execute_workflow(plan)
```

### Task Failure

```python
try:
    result = await execute_task(task)
except TaskExecutionError as e:
    # Use fallback agent
    fallback_agent = await find_fallback_agent(task)
    result = await execute_task_with_agent(task, fallback_agent)
```

### Timeout

```python
try:
    result = await asyncio.wait_for(
        execute_workflow(plan),
        timeout=300.0
    )
except asyncio.TimeoutError:
    # Notify user and save partial results
    await notify_timeout(plan, partial_results)
```

## Best Practices

### 1. Clear Task Descriptions

```python
# Good
"Collect customer purchase data from last 30 days and calculate average order value"

# Too vague
"Get data"
```

### 2. Explicit Dependencies

```json
{
  "tasks": [
    {"task_id": "collect", "dependencies": []},
    {"task_id": "analyze", "dependencies": ["collect"]},
    {"task_id": "report", "dependencies": ["analyze"]}
  ]
}
```

### 3. Health Monitoring

```python
# Check health before execution
for agent in plan.agents:
    health = await check_health(agent)
    if not health.is_healthy:
        await notify_admin(agent, health)
```

### 4. Progress Tracking

```python
# Stream progress updates
async for update in execute_workflow(plan):
    if update.type == "progress":
        await send_to_user(update)
```

### 5. Result Validation

```python
# Validate results before synthesis
for result in task_results:
    if not validate_result(result):
        await retry_task(result.task_id)
```

## Monitoring

### Metrics to Track

- **Planning Time**: Time to create execution plan
- **Agent Discovery Time**: Time to find agents
- **Health Check Duration**: Time for availability checks
- **Task Execution Time**: Time per task
- **Workflow Duration**: Total execution time
- **Success Rate**: Percentage of successful workflows
- **Agent Utilization**: Usage per agent

### Logging

```python
import logging

logger = logging.getLogger("workflow")

logger.info(f"Workflow started: {workflow_id}")
logger.info(f"Plan created: {len(plan.tasks)} tasks")
logger.info(f"Agents assigned: {len(plan.agents)}")
logger.info(f"Task completed: {task_id} in {duration}s")
logger.info(f"Workflow completed: {workflow_id} in {total_duration}s")
```

## Troubleshooting

### Planner Can't Find Agents

**Cause**: No agents registered or semantic layer down

**Solution**:
1. Check semantic layer: `docker-compose ps semantic-layer`
2. Verify agent cards exist: `ls services/semantic_layer/layer/mcp_server/agent_cards/`
3. Restart semantic layer: `docker-compose restart semantic-layer`

### Orchestrator Puts Workflow on Hold

**Cause**: Assigned agents not responding

**Solution**:
1. Check agent health: `curl http://agent:8000/health`
2. View agent logs: `docker-compose logs agent-name`
3. Restart agent: `docker-compose restart agent-name`

### Workflow Times Out

**Cause**: Tasks taking too long

**Solution**:
1. Increase timeout in client
2. Optimize agent performance
3. Break into smaller tasks
4. Use parallel execution

## See Also

- [Planner + Orchestrator Integration](planner-orchestrator-integration.md)
- [Agent Cards](agent-cards.md)
- [Semantic Layer Guide](extending-semantic-layer.md)
- [CLI Reference](cli-reference.md)
