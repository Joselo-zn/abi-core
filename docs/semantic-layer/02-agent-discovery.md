# Agent Discovery

Learn how the semantic layer finds agents automatically.

## How It Works

1. Agents register with agent cards
2. Semantic layer indexes the cards
3. Searches find agents by capability

## Search for Agents

### Using MCPToolkit (Recommended)

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Find single agent
agent = await toolkit.find_agent(query="analyze sales data")

# Recommend multiple agents
agents = await toolkit.recommend_agents(
    task_description="process transactions",
    max_agents=3
)

# Check agent capabilities
capabilities = await toolkit.check_agent_capability(
    agent_name="analyst",
    required_tasks=["analyze", "visualize"]
)

# Check agent health
health = await toolkit.check_agent_health(agent_name="analyst")
```

### Using Client Directly

```python
from abi_core.abi_mcp import client

# Search by task
agent = await client.find_agent(session, "analyze sales data")

# Search multiple
agents = await client.recommend_agents(session, "process transactions", max_agents=3)
```

## Next Steps

- [Semantic search](03-semantic-search.md)
- [MCPToolkit - Dynamic Tool Access](05-mcp-toolkit.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
