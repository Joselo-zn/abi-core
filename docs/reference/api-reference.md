# API Reference

Complete reference for ABI-Core APIs.

## AbiAgent

Base class for creating agents.

```python
from abi_core.agent.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='my-agent',
            description='Description',
            content_types=['text/plain']
        )
```

### Methods

#### `process(enriched_input)`
Processes enriched input.

**Parameters**:
- `enriched_input`: Dict with query and context

**Returns**: Dict with result

#### `stream(query, context_id, task_id)`
Responds in streaming mode.

**Parameters**:
- `query`: User query
- `context_id`: Context ID
- `task_id`: Task ID

**Returns**: AsyncGenerator with responses

## MCP Client

Client for semantic layer.

```python
from abi_core.abi_mcp import client

async with client.init_session(host, port, transport) as session:
    result = await client.find_agent(session, "description")
```

### Functions

#### `find_agent(session, description)`
Searches for an agent by description.

#### `recommend_agents(session, description, max_agents)`
Recommends multiple agents.

#### `check_agent_health(session, agent_name)`
Verifies agent health.

## Utilities

```python
from abi_core.common.utils import abi_logging, get_mcp_server_config

# Logging
abi_logging("Message")

# MCP Configuration
config = get_mcp_server_config()
```

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
