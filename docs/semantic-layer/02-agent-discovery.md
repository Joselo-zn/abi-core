# Agent Discovery

Learn how the semantic layer finds agents automatically.

## How It Works

1. Agents register with agent cards
2. Semantic layer indexes the cards
3. Searches find agents by capability

## Search for Agents

```python
from abi_core.abi_mcp import client

# Search by task
agent = await client.find_agent(session, "analyze sales data")

# Search multiple
agents = await client.recommend_agents(session, "process transactions", max_agents=3)
```

## Next Steps

- [Semantic search](03-semantic-search.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
