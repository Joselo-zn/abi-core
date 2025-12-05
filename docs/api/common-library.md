# Common Library Reference

Reference documentation for `abi_core.common` module.

## Overview

The `abi_core.common` module provides shared utilities, types, and helpers used across ABI-Core agents and services.

```python
from abi_core.common import utils, types, a2a_server
```

---

## `abi_core.common.semantic_tools`

LangChain tools for semantic layer interaction. These tools enable agents to discover other agents, check capabilities, and monitor health.

### Tools

#### `tool_find_agent(query: str)`

Find the best matching agent by natural language query.

**Parameters:**
- `query` (str) - Natural language description of desired agent

**Returns:**
- `AgentCard | None` - Matching agent card or None

**Example:**
```python
from abi_core.common.semantic_tools import tool_find_agent

# Find agent
agent = await tool_find_agent("agent that can execute stock trades")
if agent:
    print(f"Found: {agent.name} at {agent.url}")
```

---

#### `tool_recommend_agents(task_description: str, max_agents: int = 3)` ✨ NEW

Recommend multiple agents for complex tasks.

**Parameters:**
- `task_description` (str) - Description of the task
- `max_agents` (int) - Maximum agents to recommend (default: 3)

**Returns:**
- `List[Dict]` - List of recommendations with scores

**Example:**
```python
from abi_core.common.semantic_tools import tool_recommend_agents

# Get recommendations
recs = await tool_recommend_agents(
    "Analyze market data and execute trades",
    max_agents=3
)

for rec in recs:
    print(f"Agent: {rec['agent']['name']}")
    print(f"Score: {rec['relevance_score']}")
    print(f"Confidence: {rec['confidence']}")
```

---

#### `tool_check_agent_capability(agent_name: str, required_tasks: List[str])` ✨ NEW

Check if an agent has specific capabilities.

**Parameters:**
- `agent_name` (str) - Name of agent to check
- `required_tasks` (List[str]) - Required task names

**Returns:**
- `Dict` - Capability check result

**Example:**
```python
from abi_core.common.semantic_tools import tool_check_agent_capability

# Check capabilities
result = await tool_check_agent_capability(
    "trader",
    ["execute_trade", "cancel_order"]
)

if result['has_all_capabilities']:
    print("✅ Agent has all capabilities")
else:
    print(f"❌ Missing: {result['missing_tasks']}")
```

---

#### `tool_check_agent_health(agent_name: str)` ✨ NEW

Check if an agent is online and responding.

**Parameters:**
- `agent_name` (str) - Name of agent to check

**Returns:**
- `Dict` - Health status with response time

**Example:**
```python
from abi_core.common.semantic_tools import tool_check_agent_health

# Check health
health = await tool_check_agent_health("trader")

print(f"Status: {health['status']}")
if health['status'] == 'healthy':
    print(f"Response time: {health['response_time_ms']}ms")
```

---

#### `tool_list_agents(query: str)`

List all agents matching a query.

**Parameters:**
- `query` (str) - Search query

**Returns:**
- `List[AgentCard]` - List of matching agent cards

**Example:**
```python
from abi_core.common.semantic_tools import tool_list_agents

# List agents
agents = await tool_list_agents("trading")
for agent in agents:
    print(f"- {agent.name}: {agent.description}")
```

---

## `abi_core.common.utils`

Utility functions for logging, configuration, and data processing.

### Functions

#### `abi_logging(message, level='info')`

Centralized logging function for ABI-Core.

**Parameters:**
- `message` (str) - Message to log
- `level` (str) - Log level: `'debug'`, `'info'`, `'warning'`, `'error'`, `'critical'`

**Environment Variables:**
- `ABI_SETTINGS_LOGGING_DEBUG` - Enable debug logging (`true`/`false`)

**Examples:**
```python
from abi_core.common.utils import abi_logging

# Info logging (default)
abi_logging("Agent started")

# Debug logging
abi_logging("Processing query: test", "debug")

# Error logging
abi_logging("Failed to connect", "error")

# Warning logging
abi_logging("Rate limit approaching", "warning")
```

**Output Format:**
```
2025-01-21 14:30:15 - ABI - INFO - Agent started
2025-01-21 14:30:16 - ABI - DEBUG - Processing query: test
2025-01-21 14:30:17 - ABI - ERROR - Failed to connect
```

---

#### `get_mcp_server_config()`

Get MCP server configuration from environment variables.

**Returns:**
- `ServerConfig` - Server configuration object

**Environment Variables:**
- `SEMANTIC_LAYER_HOST` - MCP server host (default: `abi-semantic-layer`)
- `SEMANTIC_LAYER_PORT` - MCP server port (default: `10100`)
- `TRANSPORT` - Transport protocol (default: `sse`)

**Examples:**
```python
from abi_core.common.utils import get_mcp_server_config

# Get configuration
config = get_mcp_server_config()

print(config.host)       # 'abi-semantic-layer'
print(config.port)       # 10100
print(config.transport)  # 'sse'
print(config.url)        # 'http://abi-semantic-layer:10100/sse'
```

**Usage with MCP Client:**
```python
from abi_core.common.utils import get_mcp_server_config
from abi_core.abi_mcp import client

async def connect_to_semantic_layer():
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Use session
        result = await client.find_agent(session, "trading agent")
        return result
```

---

#### `truncate(obj, max_chars=4000)`

Convert object to JSON and truncate to maximum length.

**Parameters:**
- `obj` (Any) - Object to convert and truncate
- `max_chars` (int) - Maximum characters (default: 4000)

**Returns:**
- `str` - Truncated JSON string

**Examples:**
```python
from abi_core.common.utils import truncate

# Truncate large object
data = {"key": "value" * 1000}
truncated = truncate(data, max_chars=100)
print(truncated)  # '{"key":"valuevaluevalue...…'

# Small object (no truncation)
small_data = {"key": "value"}
result = truncate(small_data)
print(result)  # '{"key":"value"}'
```

**Use Case:**
```python
# Prevent context overflow in LLM prompts
from abi_core.common.utils import truncate

def prepare_context(data):
    # Ensure context fits within model limits
    return truncate(data, max_chars=4000)
```

---

## `abi_core.common.types`

Type definitions and Pydantic models.

### Classes

#### `ServerConfig`

Server configuration model.

**Attributes:**
- `host` (str) - Server hostname or IP
- `port` (int) - Server port (1-65535)
- `transport` (str) - Transport protocol
- `url` (str) - Complete server URL

**Examples:**
```python
from abi_core.common.types import ServerConfig

# Create configuration
config = ServerConfig(
    host="localhost",
    port=8080,
    transport="sse",
    url="http://localhost:8080/sse"
)

# Access attributes
print(config.host)       # 'localhost'
print(config.port)       # 8080
print(config.transport)  # 'sse'
print(config.url)        # 'http://localhost:8080/sse'

# Validation
try:
    invalid = ServerConfig(
        host="localhost",
        port=99999,  # Invalid port
        transport="sse",
        url="http://localhost:99999"
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

---

#### `AgentResponse`

Standard response schema for agent operations.

**Attributes:**
- `content` (str | dict) - Response content
- `is_task_complete` (bool) - Whether task is complete
- `require_user_input` (bool) - Whether user input is needed

**Examples:**
```python
from abi_core.common.types import AgentResponse

# Text response
response = AgentResponse(
    content="Task completed successfully",
    is_task_complete=True,
    require_user_input=False
)

# Structured response
response = AgentResponse(
    content={
        "result": "success",
        "data": {"order_id": "12345"}
    },
    is_task_complete=True,
    require_user_input=False
)

# Request user input
response = AgentResponse(
    content="Please confirm the amount",
    is_task_complete=False,
    require_user_input=True
)
```

**Usage in Agents:**
```python
from abi_core.common.types import AgentResponse

async def stream(self, query, context_id, task_id):
    # Process query
    result = self.process(query)
    
    # Return as AgentResponse
    response = AgentResponse(
        content=result,
        is_task_complete=True,
        require_user_input=False
    )
    
    yield {
        'content': response.content,
        'is_task_completed': response.is_task_complete,
        'require_user_input': response.require_user_input
    }
```

---

## `abi_core.common.a2a_server`

A2A server utilities for agent communication.

### Functions

#### `start_server(host, port, agent_card, agent)`

Start A2A server for an agent.

**Parameters:**
- `host` (str) - Server host (e.g., `'0.0.0.0'`)
- `port` (int) - Server port (e.g., `8000`)
- `agent_card` (str) - Path to agent card JSON file
- `agent` (AbiAgent) - Agent instance

**Examples:**
```python
from abi_core.common.a2a_server import start_server
from agents.my_agent.agent_my_agent import MyAgent

# Create agent instance
agent = MyAgent()

# Start server
start_server(
    host="0.0.0.0",
    port=8000,
    agent_card="./agent_cards/my_agent.json",
    agent=agent
)
```

**What it does:**
1. Loads agent card from JSON file
2. Creates A2A application with agent executor
3. Adds health check endpoint (`/health`)
4. Adds agent card endpoint (`/card`)
5. Adds routes listing endpoint (`/__routes`)
6. Starts Uvicorn server

**Endpoints Created:**
- `POST /stream` - Stream agent responses
- `GET /health` - Health check
- `GET /card` - Get agent card
- `GET /__routes` - List all routes
- `HEAD /` - Root endpoint

**Usage in main.py:**
```python
import os
from abi_core.common.a2a_server import start_server
from agents.my_agent.agent_my_agent import MyAgent

if __name__ == '__main__':
    # Get configuration
    host = os.getenv('AGENT_HOST', '0.0.0.0')
    port = int(os.getenv('AGENT_PORT', '8000'))
    agent_card = os.getenv('AGENT_CARD', './agent_cards/my_agent.json')
    
    # Create agent
    agent = MyAgent()
    
    # Start server
    start_server(host, port, agent_card, agent)
```

---

## `abi_core.common.agent_executor`

Agent execution wrapper for A2A protocol.

### Classes

#### `ABIAgentExecutor`

Executes ABI agents with A2A protocol support.

**Parameters:**
- `agent` (AbiAgent) - Agent instance to execute

**Methods:**
- `execute(context, event_queue)` - Execute agent with request context
- `cancel(request, event_queue)` - Cancel agent execution (not implemented)

**Examples:**
```python
from abi_core.common.agent_executor import ABIAgentExecutor
from agents.my_agent.agent_my_agent import MyAgent

# Create agent
agent = MyAgent()

# Create executor
executor = ABIAgentExecutor(agent=agent)

# Executor is used internally by A2A server
# You typically don't call it directly
```

**Internal Usage:**
```python
# In a2a_server.py
request_handler = DefaultRequestHandler(
    agent_executor=ABIAgentExecutor(agent=agent),
    task_store=InMemoryTaskStore(),
    push_config_store=push_cfg_store,
    push_sender=push_sender,
)
```

---

## `abi_core.common.workflow`

Workflow orchestration for multi-agent systems.

### Classes

#### `WorkflowNode`

Represents a single node in a workflow graph.

**Attributes:**
- `id` (str) - Unique node ID
- `task` (str) - Task description
- `result` - Task result
- `state` (Status) - Node state

**Methods:**
- `get_planner_resource()` - Get planner agent resource
- `find_agent_for_task()` - Find agent for task
- `run_node(query, task_id, context_id)` - Execute node

**Examples:**
```python
from abi_core.common.workflow import WorkflowNode

# Create node
node = WorkflowNode(
    task="Analyze market data",
    node_key="analyst",
    node_label="Market Analysis"
)

# Execute node
async for chunk in node.run_node(
    query="Analyze AAPL stock",
    task_id="task-001",
    context_id="ctx-001"
):
    print(chunk)
```

---

#### `WorkflowGraph`

Represents a workflow as a directed graph.

**Methods:**
- `add_node(node)` - Add node to graph
- `add_edge(from_node_id, to_node_id)` - Add edge between nodes
- `run_workflow(start_node_id)` - Execute workflow
- `set_node_attribute(node_id, attribute, value)` - Set node attribute
- `is_empty()` - Check if graph is empty

**Examples:**
```python
from abi_core.common.workflow import WorkflowGraph, WorkflowNode

# Create graph
graph = WorkflowGraph()

# Create nodes
node1 = WorkflowNode(task="Analyze market", node_key="analyst")
node2 = WorkflowNode(task="Execute trade", node_key="trader")

# Add nodes
graph.add_node(node1)
graph.add_node(node2)

# Add edge (analyst -> trader)
graph.add_edge(node1.id, node2.id)

# Set attributes
graph.set_node_attribute(node1.id, "query", "Analyze AAPL")
graph.set_node_attribute(node1.id, "task_id", "task-001")
graph.set_node_attribute(node1.id, "context_id", "ctx-001")

# Execute workflow
async for result in graph.run_workflow():
    print(result)
```

---

## Complete Example

Here's a complete example using multiple common utilities:

```python
import asyncio
from abi_core.common.utils import abi_logging, get_mcp_server_config, truncate
from abi_core.common.types import AgentResponse
from abi_core.common.a2a_server import start_server
from abi_core.agent.agent import AbiAgent

class MyAgent(AbiAgent):
    """Example agent using common utilities"""
    
    def __init__(self):
        super().__init__(
            agent_name='my-agent',
            description='Example agent',
            content_types=['text/plain']
        )
        abi_logging("Agent initialized")
    
    def process(self, enriched_input):
        """Process with logging and truncation"""
        query = enriched_input['query']
        
        # Log processing
        abi_logging(f"Processing: {query}")
        
        # Simulate large response
        result = {"data": "value" * 1000}
        
        # Truncate if needed
        truncated = truncate(result, max_chars=500)
        
        abi_logging("Processing complete", "info")
        
        return {
            'result': truncated,
            'query': query
        }
    
    async def stream(self, query, context_id, task_id):
        """Stream with AgentResponse"""
        try:
            # Process
            result = self.handle_input(query)
            
            # Create response
            response = AgentResponse(
                content=result['result'],
                is_task_complete=True,
                require_user_input=False
            )
            
            # Yield
            yield {
                'content': response.content,
                'is_task_completed': response.is_task_complete,
                'require_user_input': response.require_user_input
            }
            
        except Exception as e:
            abi_logging(f"Error: {e}", "error")
            
            # Error response
            response = AgentResponse(
                content=f"Error: {str(e)}",
                is_task_complete=True,
                require_user_input=False
            )
            
            yield {
                'content': response.content,
                'is_task_completed': response.is_task_complete,
                'require_user_input': response.require_user_input
            }

# Start server
if __name__ == '__main__':
    agent = MyAgent()
    
    start_server(
        host="0.0.0.0",
        port=8000,
        agent_card="./agent_cards/my_agent.json",
        agent=agent
    )
```

---

## Environment Variables Reference

### Logging

```bash
# Enable debug logging
export ABI_SETTINGS_LOGGING_DEBUG=true
```

### MCP Server

```bash
# Semantic layer configuration
export SEMANTIC_LAYER_HOST=abi-semantic-layer
export SEMANTIC_LAYER_PORT=10100
export TRANSPORT=sse
```

### Agent Server

```bash
# Agent configuration
export AGENT_HOST=0.0.0.0
export AGENT_PORT=8000
export AGENT_CARD=./agent_cards/my_agent.json
```

---

## Best Practices

### 1. Always Use abi_logging

```python
# ✅ Good
from abi_core.common.utils import abi_logging
abi_logging("Agent started")

# ❌ Bad
print("Agent started")  # Won't appear in logs
```

### 2. Get Configuration from Environment

```python
# ✅ Good
from abi_core.common.utils import get_mcp_server_config
config = get_mcp_server_config()

# ❌ Bad
config = {
    'host': 'localhost',  # Hardcoded
    'port': 8080
}
```

### 3. Use AgentResponse for Consistency

```python
# ✅ Good
from abi_core.common.types import AgentResponse

response = AgentResponse(
    content=result,
    is_task_complete=True,
    require_user_input=False
)

# ❌ Bad
response = {
    'content': result,
    'complete': True  # Inconsistent naming
}
```

### 4. Truncate Large Data

```python
# ✅ Good
from abi_core.common.utils import truncate

large_data = get_large_dataset()
safe_data = truncate(large_data, max_chars=4000)

# ❌ Bad
large_data = get_large_dataset()
# Might exceed context limits
```

---

## Next Steps

- [Agent Development](../user-guide/agent-development.md) - Build custom agents
- [CLI Reference](../user-guide/cli-reference.md) - Command line tools
- [Complete Example](../user-guide/complete-example.md) - Full walkthrough

## See Also

- [Types Reference](types.md)
- [Agent Base Classes](agent-base.md)
- [A2A Protocol](../agent_protocols.md)
