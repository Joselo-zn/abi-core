# Agent Cards

Agent cards allow agents to discover and communicate with each other.

## What is an Agent Card?

An **agent card** is a JSON document that describes:
- Agent name
- What it can do
- How to contact it
- What tasks it supports

**Analogy**: It's like a professional business card.

## Create an Agent Card

```bash
abi-core add agent-card analyst \
  --description "Analyzes sales data" \
  --url "http://localhost:8000" \
  --tasks "analyze_sales,generate_insights,calculate_metrics"
```

This creates:
```
services/semantic_layer/layer/mcp_server/agent_cards/analyst.json
```

## Agent Card Structure

```json
{
  "@context": ["https://..."],
  "@type": "Agent",
  "id": "agent://analyst",
  "name": "analyst",
  "description": "Analyzes sales data",
  "url": "http://localhost:8000",
  "supportedTasks": [
    "analyze_sales",
    "generate_insights",
    "calculate_metrics"
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b"
  },
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://analyst-default",
    "shared_secret": "UNIQUE_TOKEN"
  }
}
```

## Important Fields

### id
Unique agent identifier:
```json
"id": "agent://analyst"
```

### supportedTasks
List of tasks the agent can perform:
```json
"supportedTasks": [
  "analyze_sales",
  "generate_insights"
]
```

### url
Address where the agent can be contacted:
```json
"url": "http://localhost:8000"
```

### auth
Authentication credentials:
```json
"auth": {
  "method": "hmac_sha256",
  "shared_secret": "SECURE_TOKEN"
}
```

## Using Agent Cards

### Search for an Agent

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def find_agent(task):
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host, config.port, config.transport
    ) as session:
        result = await client.find_agent(session, task)
        return result

# Search for agent that can analyze sales
agent = await find_agent("analyze sales data")
print(agent)  # Returns: analyst
```

### List All Agents

```bash
curl http://localhost:10100/v1/agents
```

## Next Steps

- [Agent communication](03-agent-communication.md)
- [Your first multi-agent system](04-first-multi-agent-system.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
