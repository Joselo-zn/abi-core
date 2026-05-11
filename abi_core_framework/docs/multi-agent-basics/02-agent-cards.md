# Agent Cards

An agent card is a JSON file that tells the world what your agent can do and how to reach it. Other agents use it to discover and communicate with yours.

## What's in a card

```json
{
  "@context": ["https://...a2a_context.jsonld"],
  "@type": "Agent",
  "id": "agent://my_agent",
  "name": "My Agent",
  "description": "Analyzes sales data and generates insights",
  "url": "http://my-project-my-agent:8001",
  "version": "1.0.0",
  "capabilities": {
    "streaming": "True",
    "pushNotifications": "True"
  },
  "supportedTasks": [
    "analyze_sales",
    "generate_insights"
  ],
  "skills": [
    {
      "id": "analyze_sales",
      "name": "Analyze Sales",
      "description": "Analyzes sales data for trends and patterns",
      "tags": ["sales", "analysis", "data"]
    }
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b"
  },
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://my_agent-default",
    "shared_secret": "auto-generated-secret"
  }
}
```

## Key fields

| Field | What it does |
|-------|-------------|
| `id` | Unique identifier (`agent://name`) |
| `name` | Display name |
| `description` | What the agent does (used for semantic search) |
| `url` | Where to reach it (Docker container hostname + port) |
| `supportedTasks` | List of tasks it can handle |
| `skills` | Detailed skill descriptions with tags (used for discovery) |
| `auth` | HMAC credentials for secure A2A communication |

## How cards are created

The CLI generates them automatically when you add an agent:

```bash
abi-core add agent analyst --description "Analyzes sales data"
# → Creates agents/analyst/agent_cards/analyst_agent.json
```

It prompts you for tasks/skills and generates the full card with auth credentials.

## How discovery works

Agent cards are stored in the Semantic Layer (Weaviate). When an agent needs to find another:

```python
from abi_core.common.semantic_tools import tool_find_agent, tool_list_agents

# Find one agent by capability
agent_card = await tool_find_agent.ainvoke("analyze sales data")
# Returns an AgentCard object with url, name, capabilities

# Find multiple agents
agents = await tool_list_agents.ainvoke("discuss topics and share opinions")
# Returns a list of AgentCard objects
```

The search is semantic — it matches by meaning, not exact words. "analyze revenue" would find an agent described as "analyzes sales data".

## Where cards live

```
agents/my_agent/
  └── agent_cards/
      └── my_agent_agent.json    ← The card

services/semantic_layer/
  └── agent_cards/               ← All cards copied here for indexing
```

At startup, the Semantic Layer reads all cards from its `agent_cards/` directory, generates embeddings, and stores them in Weaviate for semantic search.

## Next step

👉 [Agent Communication](03-agent-communication.md)
