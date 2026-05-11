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

Agent cards are stored in the Semantic Layer. When an agent needs to find another, it searches by description:

```python
from abi_core.common.semantic_tools import tool_find_agent, tool_list_agents

# Find one agent by what it does
agent_card = await tool_find_agent.ainvoke("analyze sales data")
# Returns the agent's card with its address and capabilities

# Find multiple agents
agents = await tool_list_agents.ainvoke("discuss topics and share opinions")
# Returns a list of matching agents
```

The search matches by meaning, not exact words. "analyze revenue" finds an agent described as "analyzes sales data".

## Where cards live

```
agents/my_agent/
  └── agent_cards/
      └── my_agent_agent.json    ← The card

services/semantic_layer/
  └── agent_cards/               ← All cards copied here for indexing
```

At startup, the Semantic Layer reads all cards, converts their descriptions into searchable vectors, and stores them so other agents can find them.

## Next step

👉 [Agent Communication](03-agent-communication.md)
