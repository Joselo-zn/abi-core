# Semantic Tools API Reference

## Overview

The `abi_core.common.semantic_tools` module provides LangChain-compatible tools for agent discovery, coordination, and dynamic registration through the semantic layer.

## Installation

```python
from abi_core.common.semantic_tools import (
    tool_find_agent,
    tool_list_agents,
    tool_recommend_agents,
    tool_check_agent_capability,
    tool_check_agent_health,
    tool_register_agent
)
```

## Configuration

Tools automatically connect to the semantic layer using MCP configuration:

```python
# Configuration from environment or abi.yaml
SEMANTIC_LAYER_HOST = "semantic-layer"
SEMANTIC_LAYER_PORT = 10100
SEMANTIC_LAYER_TRANSPORT = "sse"
```

## Tools

### `tool_find_agent`

Find the best matching agent for a specific task using semantic search.

**Signature:**
```python
async def tool_find_agent(query: str) -> Optional[AgentCard]
```

**Parameters:**
- `query` (str): Natural language description of the task or agent needed

**Returns:**
- `AgentCard`: Best matching agent card, or `None` if no match found

**Example:**
```python
agent = await tool_find_agent("agent for financial data analysis")

if agent:
    print(f"Found: {agent.name}")
    print(f"Description: {agent.description}")
    print(f"Tasks: {agent.supportedTasks}")
    print(f"URL: {agent.url}")
```

**Features:**
- Semantic search using Weaviate embeddings
- Returns single best match
- Includes relevance scoring
- Authenticated via HMAC

---

### `tool_list_agents`

List all agents matching a query (uses MCP resource).

**Signature:**
```python
async def tool_list_agents(query: str) -> List[AgentCard]
```

**Parameters:**
- `query` (str): Query string (use "all" for all agents)

**Returns:**
- `List[AgentCard]`: List of matching agent cards

**Example:**
```python
# List all agents
all_agents = await tool_list_agents("all")

for agent in all_agents:
    print(f"- {agent.name}: {agent.description}")

# List specific agents
data_agents = await tool_list_agents("data")
```

---

### `tool_recommend_agents`

Recommend multiple agents for complex tasks with relevance scores.

**Signature:**
```python
async def tool_recommend_agents(
    task_description: str,
    max_agents: int = 3
) -> List[Dict[str, Any]]
```

**Parameters:**
- `task_description` (str): Description of the complex task
- `max_agents` (int, optional): Maximum number of agents to recommend (default: 3)

**Returns:**
- `List[Dict]`: List of recommendations with structure:
  ```python
  {
      "agent": AgentCard,
      "relevance_score": float,  # 0.0 to 1.0
      "confidence": str          # "high", "medium", or "low"
  }
  ```

**Example:**
```python
recommendations = await tool_recommend_agents(
    task_description="Process financial data, generate reports, and send alerts",
    max_agents=3
)

for rec in recommendations:
    agent = rec['agent']
    score = rec['relevance_score']
    confidence = rec['confidence']
    
    print(f"{agent['name']}: {score:.2f} ({confidence})")
    print(f"  Tasks: {agent['supportedTasks']}")
```

**Confidence Levels:**
- `high`: score > 0.8
- `medium`: score > 0.5
- `low`: score ≤ 0.5

---

### `tool_check_agent_capability`

Check if an agent has specific capabilities/tasks.

**Signature:**
```python
async def tool_check_agent_capability(
    agent_name: str,
    required_tasks: List[str]
) -> Dict[str, Any]
```

**Parameters:**
- `agent_name` (str): Name of the agent to check
- `required_tasks` (List[str]): List of required task names

**Returns:**
- `Dict` with structure:
  ```python
  {
      "agent": str,
      "found": bool,
      "supported_tasks": List[str],
      "missing_tasks": List[str],
      "has_all_capabilities": bool,
      "capability_coverage": float  # 0.0 to 1.0
  }
  ```

**Example:**
```python
result = await tool_check_agent_capability(
    agent_name="data_processor",
    required_tasks=["analyze data", "generate reports", "send alerts"]
)

if result['has_all_capabilities']:
    print(f"✅ Agent has all required capabilities")
else:
    print(f"⚠️ Coverage: {result['capability_coverage']:.0%}")
    print(f"Missing: {result['missing_tasks']}")
```

---

### `tool_check_agent_health`

Check if an agent is online and responding.

**Signature:**
```python
async def tool_check_agent_health(agent_name: str) -> Dict[str, Any]
```

**Parameters:**
- `agent_name` (str): Name of the agent to check

**Returns:**
- `Dict` with structure:
  ```python
  {
      "agent": str,
      "status": str,              # "healthy", "unhealthy", "timeout", "error"
      "url": str,
      "response_time_ms": float,  # Response time in milliseconds
      "status_code": int          # HTTP status code
  }
  ```

**Example:**
```python
health = await tool_check_agent_health("data_processor")

if health['status'] == 'healthy':
    print(f"✅ Agent is healthy ({health['response_time_ms']}ms)")
elif health['status'] == 'timeout':
    print(f"⏰ Agent timeout (>5s)")
else:
    print(f"❌ Agent unhealthy: {health.get('error')}")
```

**Status Values:**
- `healthy`: Agent responded with HTTP 200
- `unhealthy`: Agent responded with non-200 status
- `timeout`: No response within 5 seconds
- `error`: Connection error or exception
- `not_found`: Agent not registered

---

### `tool_register_agent` ✨ NEW

Register a new agent in the semantic layer dynamically.

**Signature:**
```python
async def tool_register_agent(agent_card_dict: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters:**
- `agent_card_dict` (Dict): Complete agent card dictionary with required fields:
  - `id` (str): Agent ID (e.g., "agent://my_agent")
  - `name` (str): Agent name
  - `description` (str): Agent description
  - `auth` (dict): Authentication credentials
    - `method` (str): Must be "hmac_sha256"
    - `key_id` (str): Key identifier
    - `shared_secret` (str): HMAC secret key
  - `supportedTasks` (List[str]): List of supported tasks
  - `skills` (List[dict]): Agent skills
  - `url` (str): Agent URL
  - `version` (str): Agent version

**Returns:**
- `Dict` with structure:
  ```python
  {
      "success": bool,
      "agent_id": str,
      "agent_name": str,
      "message": str,
      "uuid": str,
      "error": str  # Only if success=False
  }
  ```

**Example:**
```python
new_agent = {
    "id": "agent://mission_controller",
    "name": "mission_controller",
    "description": "Controls and assigns missions to field agents",
    "auth": {
        "method": "hmac_sha256",
        "key_id": "agent://mission_controller-default",
        "shared_secret": "your_generated_secret_key_here"
    },
    "supportedTasks": [
        "assign missions",
        "track mission status",
        "coordinate agents"
    ],
    "skills": [
        {
            "id": "assign_missions",
            "name": "Assign Missions",
            "description": "Assign missions to available agents",
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"]
        }
    ],
    "url": "http://mission-controller:8000",
    "version": "1.0.0"
}

result = await tool_register_agent(new_agent)

if result['success']:
    print(f"✅ Agent registered: {result['agent_name']}")
    print(f"   UUID: {result['uuid']}")
else:
    print(f"❌ Registration failed: {result['error']}")
```

**Security Requirements:**

**Authentication:**
- Agent card must include valid `auth` section
- HMAC signature verified automatically

**Authorization:**
- Only these agents can register new agents:
  - `orchestrator`
  - `planner`
  - `observer`
  - Or agents with `"permissions": ["register_agents"]` in their card

**Common Errors:**
- `"Missing required fields"`: Agent card incomplete
- `"Only hmac_sha256 authentication method is supported"`: Wrong auth method
- `"Missing shared_secret in auth section"`: No secret provided
- `"Agent not authorized to register new agents"`: Caller lacks permission
- `"Failed to generate embedding"`: Embedding service error

---

## Usage in Agents

### With LangGraph

```python
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from abi_core.common.semantic_tools import (
    tool_find_agent,
    tool_recommend_agents,
    tool_check_agent_health
)

# Create agent with semantic tools
llm = ChatOllama(model="llama3.2:3b")

agent = create_react_agent(
    llm,
    tools=[
        tool_find_agent,
        tool_recommend_agents,
        tool_check_agent_health
    ]
)

# Use agent
response = agent.invoke({
    "messages": [("user", "Find an agent for data analysis")]
})
```

### With Custom Agent

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.semantic_tools import tool_find_agent

class MyAgent(AbiAgent):
    async def process(self, input_data):
        # Find appropriate agent
        agent = await tool_find_agent(input_data['query'])
        
        if agent:
            # Delegate to found agent
            return await self.delegate_to(agent, input_data)
        else:
            # Handle locally
            return self.process_locally(input_data)
```

## Error Handling

All tools return structured error information:

```python
try:
    agent = await tool_find_agent("complex query")
    
    if agent is None:
        print("No matching agent found")
    else:
        print(f"Found: {agent.name}")
        
except Exception as e:
    print(f"Error: {e}")
```

## Best Practices

### 1. Always Check Return Values

```python
# ✅ Good
agent = await tool_find_agent(query)
if agent:
    process_with_agent(agent)
else:
    handle_no_agent()

# ❌ Bad
agent = await tool_find_agent(query)
process_with_agent(agent)  # May be None!
```

### 2. Use Appropriate Tool for Task

```python
# Single agent needed
agent = await tool_find_agent("data analysis")

# Multiple agents for complex task
agents = await tool_recommend_agents("process and analyze data", max_agents=3)

# Check specific capability
can_do = await tool_check_agent_capability("processor", ["analyze", "report"])
```

### 3. Handle Timeouts

```python
import asyncio

try:
    health = await asyncio.wait_for(
        tool_check_agent_health("agent_name"),
        timeout=10.0
    )
except asyncio.TimeoutError:
    print("Health check timed out")
```

### 4. Secure Agent Registration

```python
# Generate secure secret
import secrets
shared_secret = secrets.token_urlsafe(32)

# Store securely (environment variable, secrets manager)
os.environ['NEW_AGENT_SECRET'] = shared_secret

# Use in agent card
agent_card = {
    "auth": {
        "shared_secret": os.getenv('NEW_AGENT_SECRET')
    }
}
```

## See Also

- [Extending Semantic Layer](../user-guide/extending-semantic-layer.md)
- [Agent Development](../user-guide/agent-development.md)
- [Security Guide](../user-guide/security.md)
- [MCP Protocol](https://modelcontextprotocol.io/)
