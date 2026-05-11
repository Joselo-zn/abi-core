# What is the Semantic Layer?

A service that stores information about all your agents, so they can find each other by describing what they need — not by knowing exact addresses.

## Without it

```python
# Hardcoded. Breaks when you add/move agents.
response = await call("http://analyst:8001", "analyze sales")
response = await call("http://reporter:8002", "write report")
```

## With it

```python
from abi_core.common.semantic_tools import tool_find_agent

# Searches by meaning. Works even if you say it differently.
agent = await tool_find_agent.ainvoke("examine revenue data")
# → Returns the analyst agent with its address
```

## What it includes

| Component | What it does |
|-----------|-------------|
| Weaviate | Database that understands meaning (finds similar descriptions) |
| MCP Server | Provides tools like find_agent, register_agent, search_tools |
| Embedding Mesh | Converts text descriptions into searchable numbers |
| Agent Cards | JSON files describing what each agent can do |
| Tool Cards | JSON files describing available tools |
| Tool Cards | JSON files describing available tools |

## Add it to your project

```bash
abi-core create project my-app --with-semantic-layer
```

Or add to an existing project:

```bash
abi-core add service semantic-layer
```

This creates:

```
services/semantic_layer/
├── embedding_mesh/     ← Embedding generation + Weaviate CRUD
├── agent_cards/        ← Agent card JSON files (auto-indexed)
├── tool_cards/         ← Tool card JSON files (auto-indexed)
├── config/
├── main.py
├── Dockerfile
└── requirements.txt
```

## How it works at startup

1. Semantic Layer reads all JSON files from `agent_cards/` and `tool_cards/`
2. Generates embeddings for each card's description + skills + tags
3. Stores them in Weaviate collections
4. Exposes MCP tools for search (`find_agent`, `list_agents`, `search_tool_registry`)

## Use it from your agent

```python
from abi_core.common.semantic_tools import tool_find_agent, tool_list_agents, MCPToolkit

# Find one agent
agent = await tool_find_agent.ainvoke("write reports")

# Find multiple agents
agents = await tool_list_agents.ainvoke("discuss and share opinions")

# Call any custom MCP tool
toolkit = MCPToolkit()
result = await toolkit.store_document(content="...", metadata={...})
```

## Next step

👉 [Agent Discovery](02-agent-discovery.md)
