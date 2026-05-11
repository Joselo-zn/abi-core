# Agent Discovery

How agents find each other through the Semantic Layer.

## The tools

ABI-Core provides ready-made functions for finding agents. Import them from `abi_core.common.semantic_tools`:

| Tool | What it does |
|------|-------------|
| `tool_find_agent` | Find one agent matching a description |
| `tool_list_agents` | Find multiple agents matching a description |
| `tool_recommend_agents` | Recommend agents for a complex task (with scores) |
| `tool_check_agent_capability` | Check if an agent supports specific tasks |
| `tool_check_agent_health` | Ping an agent to see if it's alive |

## Find one agent

```python
from abi_core.common.semantic_tools import tool_find_agent

agent_card = await tool_find_agent.ainvoke("analyze financial data")

if agent_card:
    print(agent_card.name)  # "analyst"
    print(agent_card.url)   # "http://my-project-analyst:8001"
```

The search is semantic — "examine revenue" matches an agent described as "analyzes sales data".

## Find multiple agents

```python
from abi_core.common.semantic_tools import tool_list_agents

agents = await tool_list_agents.ainvoke("share opinions and discuss topics")
# Returns a list of AgentCard objects

for agent in agents:
    print(f"{agent.name} at {agent.url}")
```

## Check if an agent is alive

```python
from abi_core.common.semantic_tools import tool_check_agent_health

health = await tool_check_agent_health.ainvoke("analyst")
# {"agent": "analyst", "status": "healthy", "response_time_ms": 45}
```

## How matching works

The Semantic Layer generates embeddings from:
- Agent `description`
- `supportedTasks` list
- `skills[].description` and `skills[].tags`

When you search, your query is also embedded and compared by cosine similarity. The closest match wins.

This means:
- "analyze sales" → finds "revenue analysis agent"
- "write a report" → finds "document generation agent"
- "translate to Spanish" → finds "multilingual agent"

## Register a new agent at runtime

```python
from abi_core.common.semantic_tools import tool_register_agent

await tool_register_agent.ainvoke({
    "id": "agent://new_agent",
    "name": "new_agent",
    "description": "Does something new",
    "url": "http://new-agent:8005",
    "supportedTasks": ["new_task"],
    "auth": {"method": "hmac_sha256", "key_id": "...", "shared_secret": "..."}
})
```

This is how the Builder agent registers ephemeral agents dynamically.

## Next step

👉 [Semantic Search](03-semantic-search.md)
