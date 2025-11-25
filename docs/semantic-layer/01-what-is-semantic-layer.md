# What is the Semantic Layer?

The semantic layer is the "intelligent directory" that enables automatic agent discovery.

## The Problem Without Semantic Layer

```python
# You have to know exactly which agent to call
call_agent("http://analyst:8000", "analyze data")
call_agent("http://reporter:8001", "generate report")
# What if URLs change?
# What if you add new agents?
```

## The Solution: Semantic Layer

```python
# Automatically finds the right agent
agent = find_agent("I need to analyze data")
# Returns: Analyst Agent

agent = find_agent("I need to generate a report")
# Returns: Reporter Agent
```

## Components

### 1. MCP Server
Server that manages agent cards and searches.

### 2. Weaviate
Vector database for semantic search.

### 3. Agent Cards
Metadata for each agent.

## Add Semantic Layer

```bash
abi-core add semantic-layer
```

This creates:
```
services/semantic_layer/
├── layer/
│   ├── mcp_server/        # MCP server
│   │   └── agent_cards/   # Agent cards
│   └── embedding_mesh/    # Embeddings
├── Dockerfile
└── requirements.txt
```

## Use the Semantic Layer

### Search for Agent

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def search(description):
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host, config.port, config.transport
    ) as session:
        result = await client.find_agent(session, description)
        return result

# Search
agent = await search("agent that analyzes sales")
```

### List Agents

```bash
curl http://localhost:10100/v1/agents
```

## Next Steps

- [Agent discovery](02-agent-discovery.md)
- [Semantic search](03-semantic-search.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
