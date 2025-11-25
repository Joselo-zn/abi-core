# Planner + Orchestrator Integration Guide

## Overview

The Planner and Orchestrator agents work together to handle complex multi-agent workflows. This guide explains their integration, communication flow, and usage patterns.

## Architecture

```
User Query
    ↓
┌─────────────────┐
│ Planner Agent   │ ← Decomposes query, asks clarifications
└────────┬────────┘
         │ Plan JSON
         ↓
┌─────────────────┐
│ Orchestrator    │ ← Checks health, executes workflow
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Worker Agents   │ ← Execute individual tasks
└─────────────────┘
```

## Communication Flow

### Phase 1: Planning

1. **User sends query** to Planner Agent
2. **Planner analyzes** using Chain of Thought reasoning
3. **Two possible outcomes:**
   - **Needs clarification**: Planner asks questions
   - **Ready**: Planner creates execution plan

#### Clarification Flow

```json
{
  "status": "needs_clarification",
  "questions": [
    {
      "id": "q1",
      "question": "What time range for analysis?",
      "type": "required",
      "options": ["7 days", "30 days", "custom"]
    }
  ],
  "partial_understanding": "User wants data analysis"
}
```

User provides answers:
```
q1: 30 days
```

Planner receives answers and generates plan.

#### Plan Generation

Planner uses semantic tools to find agents:
- `tool_find_agent(task_description)` - Find best agent
- `tool_recommend_agents(task_description, max_agents=N)` - Get recommendations

Output plan format:
```json
{
  "status": "ready",
  "plan": {
    "objective": "Analyze market trends and create report",
    "tasks": [
      {
        "task_id": "task_1",
        "description": "Collect market data from sources",
        "agents": [
          {
            "name": "observer_agent",
            "id": "agent://observer_agent",
            "url": "http://observer:8000"
          }
        ],
        "agent_count": 1,
        "dependencies": [],
        "requires_clarification": false
      },
      {
        "task_id": "task_2",
        "description": "Analyze collected data",
        "agents": [
          {
            "name": "actor_agent",
            "id": "agent://actor_agent",
            "url": "http://actor:8000"
          }
        ],
        "agent_count": 1,
        "dependencies": ["task_1"],
        "requires_clarification": false
      }
    ],
    "execution_strategy": "sequential"
  }
}
```

### Phase 2: Orchestration

1. **Orchestrator receives plan** from Planner
2. **Health checks** all assigned agents with retries
3. **Two possible outcomes:**
   - **All healthy**: Execute workflow
   - **Some unavailable**: Put workflow on hold

#### Health Check Flow

Orchestrator checks each agent:
```python
for agent in plan.agents:
    health = await tool_check_agent_health(agent.name)
    if health['status'] != 'healthy':
        # Retry with exponential backoff
        # 1s, 2s, 4s, 8s, 16s
```

If agents unavailable after 5 retries:
```json
{
  "status": "on_hold",
  "unavailable_agents": [
    {
      "agent": "observer_agent",
      "retries": 5,
      "last_status": "unreachable"
    }
  ]
}
```

#### Workflow Execution

If all agents healthy:

1. **Create WorkflowGraph** from plan
2. **Execute with LangGraph** state machine
3. **Stream progress** updates every 5 seconds
4. **Collect results** from each node
5. **Synthesize final output** using LLM

```python
# Create workflow
workflow = create_workflow_from_plan(plan)

# Execute with monitoring
async for chunk in execute_with_monitoring(workflow):
    # Stream to user
    yield chunk

# Synthesize results
synthesis = await synthesize_results(results, plan)
```

### Phase 3: Result Synthesis

Orchestrator uses LLM to synthesize results:

```python
prompt = ORCHESTRATOR_COT_INSTRUCTIONS.format(
    task_data=json.dumps({
        "plan": plan,
        "results": results
    })
)

synthesis = await llm.ainvoke([HumanMessage(content=prompt)])
```

Output format:
```markdown
## Multi-Agent Task Summary

### Task Overview
- User Query: Analyze market trends
- Subtasks: 2 tasks completed

### Agent Workflow
- Observer Agent: Collected data from 5 sources
- Actor Agent: Analyzed trends, identified 3 key patterns

### Results Summary
- Market shows upward trend in Q4
- Competitor activity increased 15%
- Recommended actions: ...

### Final Output
Based on the analysis...
```

## Q&A Flow Between Agents

Planner can ask Orchestrator questions during planning:

```python
# Planner asks
question = {
    "type": "clarification",
    "question": "Is agent X available for this task?",
    "context": {...}
}

# Orchestrator handles via ORCHESTRATOR_QA_COT_PLANNER
response = await handle_planner_question(question)

# Three possible responses:
# 1. Orchestrator answers directly
{
    "can_answer": "yes",
    "answer": "Agent X is available",
    "source": "orchestrator"
}

# 2. Must ask user
{
    "can_answer": "need_user",
    "user_question": "Do you want to use Agent X?",
    "question_type": "required"
}

# 3. Need to use tool
{
    "can_answer": "yes",
    "answer": "Checked via tool",
    "source": "tool"
}
```

## Usage Examples

### Example 1: Simple Query

```python
import httpx
import json

async def simple_workflow():
    # Step 1: Send to Planner
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11437/stream",
            json={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Analyze sales data"}],
                    "messageId": "task-001",
                    "contextId": "session-001"
                }
            }
        )
        
        # Get plan
        plan = extract_plan_from_response(response)
        
        # Step 2: Send to Orchestrator
        response = await client.post(
            "http://localhost:8002/stream",
            json={
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": json.dumps({"plan": plan})}],
                    "messageId": "task-001",
                    "contextId": "session-001"
                }
            }
        )
        
        # Stream results
        async for chunk in response.aiter_lines():
            print(chunk)
```

### Example 2: With Clarification

```python
async def workflow_with_clarification():
    # Step 1: Initial query
    response = await send_to_planner("Analyze data")
    
    # Step 2: Handle clarification
    if response.status == "needs_clarification":
        questions = response.questions
        
        # Get user answers
        answers = get_user_answers(questions)
        
        # Send answers back
        response = await send_to_planner(format_answers(answers))
    
    # Step 3: Execute plan
    plan = response.plan
    results = await send_to_orchestrator(plan)
    
    return results
```

### Example 3: Error Handling

```python
async def workflow_with_error_handling():
    try:
        # Planning phase
        plan = await get_plan_from_planner(query)
        
        # Orchestration phase
        result = await execute_via_orchestrator(plan)
        
        # Check status
        if result.status == "on_hold":
            # Agents unavailable
            unavailable = result.unavailable_agents
            
            # Notify user
            notify_user(f"Waiting for agents: {unavailable}")
            
            # Retry later or use fallback
            await retry_with_backoff(plan)
        
        elif result.status == "completed":
            # Success
            return result.synthesis
        
    except Exception as e:
        # Handle errors
        logger.error(f"Workflow failed: {e}")
        return fallback_response()
```

## Configuration

### Planner Configuration

```bash
# Environment variables
MODEL_NAME=qwen2.5:3b
AGENT_HOST=0.0.0.0
AGENT_PORT=11437
AGENT_CARD=/app/agent_cards/planner_agent.json
```

**Agent Card**: Automatically generated with:
- **ID**: `agent://planner_agent`
- **Auth**: HMAC-SHA256 with unique `shared_secret`
- **Tasks**: `decompose complex queries`, `assign agents to tasks`, `create execution plans`, `manage task dependencies`

### Orchestrator Configuration

```bash
# Environment variables
MODEL_NAME=qwen2.5:3b
AGENT_HOST=0.0.0.0
AGENT_PORT=8002
AGENT_CARD=/app/agent_cards/orchestrator_agent.json
WEB_INTERFACE_PORT=8083
```

**Agent Card**: Automatically generated with:
- **ID**: `agent://abi_orchestrator_agent`
- **Auth**: HMAC-SHA256 with unique `shared_secret`
- **Tasks**: `coordinate workflows`, `execute multi-agent plans`, `monitor task execution`, `synthesize results`

### Semantic Layer Configuration

Both agents require access to the semantic layer (MCP server):

```bash
# MCP Server
MCP_HOST=semantic-layer
MCP_PORT=10100
MCP_TRANSPORT=sse
```

### Agent Card Security

Agent cards are generated with cryptographic authentication:

```json
{
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://planner_agent-default",
    "shared_secret": "UNIQUE_32_BYTE_TOKEN"
  }
}
```

- **Generated at build time**: No runtime initialization
- **Unique per agent**: Each agent has its own secret
- **Immutable**: Stored in agent card JSON
- **Automatic registration**: Copied to semantic layer during setup

See [Agent Cards Guide](agent-cards.md) for more details.

## Best Practices

### 1. Always Check Agent Health

Before executing workflows, Orchestrator checks agent health with retries:
- 5 retry attempts
- Exponential backoff (1s, 2s, 4s, 8s, 16s)
- Clear error messages if unavailable

### 2. Use Clarification Flow

Planner should ask questions when:
- Requirements are ambiguous
- Multiple execution paths possible
- User preferences needed

### 3. Structured Plans

Plans should include:
- Clear task descriptions
- Specific agent assignments
- Explicit dependencies
- Execution strategy

### 4. Result Synthesis

Orchestrator synthesizes results to:
- Provide coherent summary
- Hide implementation details
- Present actionable insights

### 5. Error Handling

Handle common scenarios:
- Agents unavailable → Put on hold
- Task failures → Retry or fallback
- Timeout → Notify user

## Monitoring

### Planner Metrics

- Planning time
- Clarification rate
- Agent assignment accuracy
- Plan success rate

### Orchestrator Metrics

- Workflow execution time
- Agent health check duration
- Task completion rate
- Result synthesis quality

## Troubleshooting

### Issue: Planner can't find agents

**Cause**: Semantic layer not accessible or no agents registered

**Solution**:
1. Check MCP server is running
2. Verify agents are registered in semantic layer
3. Check network connectivity

### Issue: Orchestrator puts workflow on hold

**Cause**: Assigned agents are not responding

**Solution**:
1. Check agent health manually
2. Verify agent containers are running
3. Check network connectivity
4. Review agent logs

### Issue: Plan execution fails

**Cause**: Task dependencies not met or agent errors

**Solution**:
1. Review plan structure
2. Check dependency order
3. Verify agent capabilities
4. Review agent logs

## Advanced Topics

### Custom Execution Strategies

Plans can specify execution strategies:
- `sequential`: Tasks run one after another
- `parallel`: Independent tasks run concurrently
- `hybrid`: Mix of sequential and parallel

### Dynamic Agent Selection

Planner uses semantic search to find best agents:
- Embedding-based similarity
- Capability matching
- Load balancing

### Workflow State Management

Orchestrator maintains workflow state:
- In-memory for development
- Redis for production (TODO)
- Supports pause/resume

### Result Caching

Cache results for efficiency:
- LRU cache for workflow states
- Redis for distributed caching (TODO)

## See Also

- [Planner Agent README](../../src/abi_core/abi_agents/planner/README.md)
- [Orchestrator Agent README](../../src/abi_core/abi_agents/orchestrator/README.md)
- [Semantic Tools API](../api/semantic-tools.md)
- [Workflow System](../api/workflow.md)
