# Agent Communication & Protocols (A2A + MCP)

## Overview

This document outlines the communication protocols used in ABI-Core for inter-agent coordination and semantic discovery. The system uses two complementary protocols:

* **A2A** (Agent-to-Agent Protocol): Enables direct agent-to-agent communication with streaming support
* **MCP** (Model Context Protocol): Provides semantic layer for agent discovery and capability routing

## Implementation in ABI-Core

ABI-Core implements these protocols through:

1. **Semantic Layer** - MCP server for agent discovery (`services/semantic_layer/`)
2. **Agent Cards** - Structured metadata for agent capabilities
3. **A2A Client** - Built-in support for agent-to-agent communication
4. **Streaming Protocol** - Real-time message streaming via SSE/HTTP

---

## 1. A2A – Agent-to-Agent Protocol

A2A enables direct communication between agents with support for:

* **Streaming messages** - Real-time response streaming
* **Task management** - Context and task tracking
* **Artifacts** - Structured data exchange
* **State transitions** - Task lifecycle management

### 1.1 Message Structure

Messages follow the A2A protocol specification:

```python
from a2a.types import MessageSendParams, SendStreamingMessageRequest
from uuid import uuid4

# Create message
request = SendStreamingMessageRequest(
    id=str(uuid4()),
    params=MessageSendParams(
        message={
            'role': 'user',
            'parts': [{'kind': 'text', 'text': 'Execute trade for AAPL'}],
            'messageId': 'msg-001',
            'contextId': 'ctx-001'
        }
    )
)
```

### 1.2 Sending Messages

```python
from a2a.client import A2AClient
from a2a.types import AgentCard
import httpx

# Get target agent card
agent_card = AgentCard(
    id="agent://trader",
    name="trader",
    url="http://trader-agent:8000"
)

# Send message
async with httpx.AsyncClient() as http_client:
    a2a_client = A2AClient(http_client, agent_card)
    
    async for response in a2a_client.send_message_stream(request):
        if hasattr(response.root.result, 'artifact'):
            result = response.root.result.artifact
            print(f"Received: {result}")
```

### 1.3 Response Types

Agents can return different response types:

```python
# Text response
yield {
    'content': 'Trade executed successfully',
    'response_type': 'text',
    'is_task_completed': True,
    'require_user_input': False
}

# Data response
yield {
    'content': {'order_id': '12345', 'status': 'filled'},
    'response_type': 'data',
    'is_task_completed': True,
    'require_user_input': False
}

# Request user input
yield {
    'content': 'Please confirm trade amount',
    'response_type': 'text',
    'is_task_completed': False,
    'require_user_input': True
}
```

---

## 2. MCP – Model Context Protocol

MCP provides the semantic layer for agent discovery and capability routing.

### 2.1 Core Components

**MCP Server** (`services/semantic_layer/layer/mcp_server/`)
- Hosts agent cards
- Provides discovery tools
- Manages agent registry

**Agent Cards** (`agent_cards/*.json`)
- Structured metadata about agent capabilities
- Semantic descriptions for discovery
- Connection information (URL, ports)

**Discovery Tools**
- `find_agent` - Find agent by natural language query
- `get_agent_card` - Get specific agent metadata
- `list_agents` - List all registered agents

### 2.2 Agent Discovery

**Finding Agents:**

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
import json

async def find_trading_agent():
    """Find agent capable of trading"""
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Natural language query
        result = await client.find_agent(
            session,
            "Find an agent that can execute stock trades"
        )
        
        # Parse result
        agent_card = json.loads(result.content[0].text)
        return agent_card
```

**Via HTTP:**

```bash
curl -X POST http://localhost:8765/v1/tools/find_agent \
  -H "Content-Type: application/json" \
  -H "X-ABI-Agent-ID: agent://client" \
  -d '{"query": "Find an agent for market analysis"}'
```

### 2.3 Agent Cards

Agent cards define agent capabilities:

```json
{
  "@context": ["https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"],
  "@type": "Agent",
  "id": "agent://trader",
  "name": "trader",
  "description": "Executes trading operations",
  "url": "http://trader-agent:8000",
  "version": "1.0.0",
  "capabilities": {
    "streaming": "True",
    "pushNotifications": "True"
  },
  "supportedTasks": [
    "execute_trade",
    "cancel_order",
    "check_position"
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "temperature": 0.1
  },
  "skills": [
    {
      "id": "execute_trade",
      "name": "Execute Trade",
      "description": "Execute stock trades",
      "tags": ["trading", "execution"],
      "examples": ["Buy 100 shares of AAPL"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ]
}
```

**Creating Agent Cards:**

```bash
abi-core add agent-card trader \
  --description "Executes trading operations" \
  --url "http://trader-agent:8000" \
  --tasks "execute_trade,cancel_order,check_position"
```

---

## 3. Complete Workflow Example

Here's how A2A and MCP work together:

```python
import asyncio
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
from uuid import uuid4
import httpx
import json

async def execute_with_discovery():
    """Find agent via MCP, then communicate via A2A"""
    
    # Step 1: Discover agent via MCP
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Find trading agent
        result = await client.find_agent(
            session,
            "agent that executes trades"
        )
        
        agent_card_data = json.loads(result.content[0].text)
        agent_card = AgentCard(**agent_card_data)
        print(f"Found: {agent_card.name} at {agent_card.url}")
    
    # Step 2: Communicate via A2A
    async with httpx.AsyncClient() as http_client:
        a2a_client = A2AClient(http_client, agent_card)
        
        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{
                        'kind': 'text',
                        'text': 'Buy 100 shares of AAPL'
                    }],
                    'messageId': str(uuid4()),
                    'contextId': str(uuid4())
                }
            )
        )
        
        # Stream response
        async for response in a2a_client.send_message_stream(request):
            if hasattr(response.root.result, 'artifact'):
                result = response.root.result.artifact
                print(f"Trade result: {result}")
                return result

# Run
asyncio.run(execute_with_discovery())
```

## 4. Security & Validation

### Semantic Access Control

The semantic layer enforces access control via OPA policies:

```python
from abi_core.semantic.semantic_access_validator import validate_semantic_access

@validate_semantic_access
def find_agent(query: str, _request_context: dict = None):
    """Find agent with access control"""
    # Only authorized agents can discover others
    # Policy checks:
    # - Agent registration
    # - Blacklist status
    # - Rate limits
    # - IP restrictions
    pass
```

### Agent Authentication

Agents authenticate via headers:

```bash
curl -X POST http://localhost:8765/v1/tools/find_agent \
  -H "X-ABI-Agent-ID: agent://client" \
  -H "X-ABI-Signature: <signature>" \
  -H "X-ABI-Timestamp: <timestamp>" \
  -d '{"query": "find agent"}'
```

### Audit Logging

All agent interactions are logged:

```json
{
  "timestamp": "2025-01-21T10:30:00Z",
  "source_agent": "agent://orchestrator",
  "target_agent": "agent://trader",
  "action": "find_agent",
  "query": "agent that executes trades",
  "result": "success",
  "risk_score": 0.2
}
```

## 5. Transport Protocols

### HTTP/SSE (Default)

```python
# MCP uses SSE for streaming
async with sse_client(url) as (read_stream, write_stream):
    async with ClientSession(
        read_stream=read_stream,
        write_stream=write_stream
    ) as session:
        # Use session
        pass
```

### WebSocket (Future)

WebSocket support planned for future releases.

## 6. Best Practices

### 1. Always Use Semantic Discovery

```python
# ✅ Good - Discover agent dynamically
agent_card = await find_agent("trading agent")
result = await call_agent(agent_card, query)

# ❌ Bad - Hardcode agent URLs
result = await call_agent("http://trader:8000", query)
```

### 2. Handle Streaming Properly

```python
# ✅ Good - Process stream
async for response in a2a_client.send_message_stream(request):
    if hasattr(response.root.result, 'artifact'):
        process(response.root.result.artifact)

# ❌ Bad - Block on stream
result = await a2a_client.send_message_stream(request)
```

### 3. Include Context IDs

```python
# ✅ Good - Track context
context_id = str(uuid4())
message = {
    'contextId': context_id,
    'messageId': str(uuid4()),
    # ...
}

# ❌ Bad - No context tracking
message = {
    'text': 'query',
    # Missing context
}
```

## 7. Next Steps

- [Complete Example](user-guide/complete-example.md) - Full workflow
- [Agent Development](user-guide/agent-development.md) - Build agents
- [Semantic Enrichment](user-guide/semantic-enrichment.md) - Understand discovery

## Resources

- [A2A Protocol Specification](https://github.com/GoogleCloudPlatform/a2a-llm)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [Agent Cards Schema](https://github.com/GoogleCloudPlatform/a2a-llm/tree/main/a2a/ontology)
