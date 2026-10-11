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
from abi_core.common.agent_card_loader import get_agent_url
from abi_core.common.semantic_tools import tool_find_agent

agent_card = await tool_find_agent.ainvoke("analyze financial data")

if agent_card:
    print(agent_card.name)          # "analyst"
    print(get_agent_url(agent_card))  # "http://my-project-analyst:8001"
```

`AgentCard` is a2a-sdk's protobuf type (since a2a-sdk 1.0) — it has no `.url`
attribute. Use `get_agent_url(card)` (or `card.supported_interfaces[0].url`
directly) to read the address.

The search is semantic — "examine revenue" matches an agent described as "analyzes sales data".

Pass `exclude_ephemeral=True` to leave ephemeral agents — the ones created on demand for a single plan — out of the search. Use it whenever you're looking for a long-lived agent to hand new work to: an ephemeral belongs to the run that created it.

```python
agent_card = await tool_find_agent.ainvoke({"query": "planner", "exclude_ephemeral": True})
```

To look up one ephemeral by its exact name, use the semantic layer's MCP tool `get_ephemeral_card`; it returns the card without its `auth` block:

```python
from abi_core.common.semantic_tools import MCPToolkit

card = await MCPToolkit().call("get_ephemeral_card", agent_name="<ephemeral-agent-name>")
```

## Find multiple agents

```python
from abi_core.common.agent_card_loader import get_agent_url
from abi_core.common.semantic_tools import tool_list_agents

agents = await tool_list_agents.ainvoke("share opinions and discuss topics")
# Returns a list of AgentCard objects, best match first (up to 5)

agents = await tool_list_agents.ainvoke({"query": "share opinions", "max_agents": 10})

for agent in agents:
    print(f"{agent.name} at {get_agent_url(agent)}")
```

`tool_list_agents` calls the semantic layer's `recommend_agents` tool, so the [semantic access policy](../security/02-opa-policies.md) checks `recommend_agents`: if your agent card restricts `security.allowed_mcp_tools`, include it.

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

await tool_register_agent.ainvoke({"agent_card_dict": {
    "id": "agent://new_agent",
    "name": "new_agent",
    "description": "Does something new",
    "url": "http://new-agent:8005",
    "supportedTasks": ["new_task"],
    "auth": {"method": "hmac_sha256", "key_id": "...", "shared_secret": "..."}
}})
```

This is how the Builder agent registers ephemeral agents dynamically.

## Next step

👉 [Semantic Search](03-semantic-search.md)
