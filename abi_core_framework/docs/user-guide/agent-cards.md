# Agent Cards

## Overview

Agent cards are JSON-LD documents that describe an agent's capabilities, authentication, and metadata. They enable semantic discovery and secure agent-to-agent communication.

## Structure

Agent cards follow the A2A (Agent-to-Agent) protocol specification and include:

```json
{
  "@context": [
    "https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"
  ],
  "@type": "Agent",
  "id": "agent://my_agent",
  "name": "My Agent",
  "description": "Specialized agent for data analysis",
  "url": "http://my-agent:8000",
  "version": "1.0.0",
  "capabilities": {
    "streaming": "True",
    "pushNotifications": "True",
    "stateTransitionHistory": "False"
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "supportedTasks": [
    "analyze_data",
    "generate_report",
    "visualize_results"
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "temperature": 0.1
  },
  "skills": [
    {
      "id": "analyze_data",
      "name": "Analyze Data",
      "description": "Analyze Data functionality for My Agent",
      "tags": ["analyze_data", "processing", "analysis"],
      "examples": ["Execute analyze_data operation"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ],
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://my_agent-default",
    "shared_secret": "UNIQUE_TOKEN_HERE"
  },
  "metadata": {
    "created": "2025-01-15T10:30:00Z",
    "generator": "abi-core-cli",
    "version": "1.4.0"
  }
}
```

## Key Fields

### Identity

- **`@context`**: JSON-LD context for semantic interpretation
- **`@type`**: Always "Agent" for agent cards
- **`id`**: Unique agent identifier (URI format: `agent://agent_name`)
- **`name`**: Human-readable agent name
- **`description`**: Brief description of agent's purpose

### Connectivity

- **`url`**: Agent's HTTP endpoint for A2A communication
- **`version`**: Agent card version (semantic versioning)

### Capabilities

- **`capabilities`**: Features supported by the agent
  - `streaming`: Real-time response streaming
  - `pushNotifications`: Proactive notifications
  - `stateTransitionHistory`: State tracking
- **`defaultInputModes`**: Accepted input formats
- **`defaultOutputModes`**: Produced output formats

### Tasks & Skills

- **`supportedTasks`**: List of task identifiers the agent can perform
- **`skills`**: Detailed skill descriptions with:
  - `id`: Unique skill identifier
  - `name`: Human-readable skill name
  - `description`: What the skill does
  - `tags`: Searchable keywords
  - `examples`: Usage examples
  - `inputModes`: Accepted input formats
  - `outputModes`: Produced output formats

### LLM Configuration

- **`llmConfig`**: Language model settings
  - `provider`: LLM provider (e.g., "ollama", "openai")
  - `model`: Model identifier
  - `temperature`: Sampling temperature

### Authentication

- **`auth`**: Security credentials
  - `method`: Authentication method (e.g., "hmac_sha256")
  - `key_id`: Key identifier for authentication
  - `shared_secret`: Secret token for signing requests

### Metadata

- **`metadata`**: Additional information
  - `created`: Creation timestamp (ISO 8601)
  - `generator`: Tool that created the card
  - `version`: Metadata version

## Automatic Generation

ABI-Core automatically generates signed agent cards when you:

### 1. Add Orchestration Layer

```bash
abi-core add agentic-orchestration-layer
```

Creates signed cards for:
- **Planner Agent** (`agent://planner_agent`)
- **Orchestrator Agent** (`agent://abi_orchestrator_agent`)

Cards are saved to:
- `agents/planner/agent_cards/planner_agent.json`
- `agents/orchestrator/agent_cards/orchestrator_agent.json`
- `services/semantic_layer/layer/mcp_server/agent_cards/` (both)

### 2. Add Agent Card Manually

```bash
abi-core add agent-card my-agent \
  --description "Data analysis agent" \
  --url "http://my-agent:8000" \
  --tasks "analyze_data,generate_report"
```

Creates signed card at:
- `services/semantic_layer/layer/mcp_server/agent_cards/my_agent.json`
- `agents/my_agent/agent_cards/my_agent.json` (if agent exists)

## Authentication

Agent cards include cryptographic authentication credentials:

### HMAC-SHA256

The default authentication method uses HMAC-SHA256:

1. **Key ID**: Unique identifier for the key (`agent://agent_name-default`)
2. **Shared Secret**: 32-byte random token generated with `secrets.token_urlsafe(32)`

### Token Generation

Tokens are generated at build time:

```python
from secrets import token_urlsafe

shared_secret = token_urlsafe(32)  # e.g., "xK9mP2vL..."
```

### Security Properties

- **Unique per agent**: Each agent has its own secret
- **Immutable**: Generated once during setup
- **Persistent**: Stored in agent card JSON
- **Build-time**: No runtime initialization needed

## Semantic Discovery

Agent cards enable semantic discovery through the semantic layer:

### Registration

Cards are automatically registered when:
1. Copied to `services/semantic_layer/layer/mcp_server/agent_cards/`
2. Semantic layer starts and scans the directory
3. Cards are indexed with vector embeddings

### Search

Agents can find each other using semantic search:

```python
# Planner finding agents for a task
agents = await tool_find_agent("analyze customer data")
# Returns: [{"name": "analyzer", "url": "http://analyzer:8000", ...}]

# Get multiple recommendations
agents = await tool_recommend_agents("process transactions", max_agents=3)
# Returns: Top 3 agents ranked by semantic similarity
```

### Matching

The semantic layer matches tasks to agents using:
- **Task descriptions**: Semantic similarity to `supportedTasks`
- **Skills**: Matching against skill descriptions and tags
- **Embeddings**: Vector similarity search with `nomic-embed-text`

## Card Lifecycle

### 1. Generation

```bash
# Automatic (orchestration layer)
abi-core add agentic-orchestration-layer

# Manual (custom agent)
abi-core add agent-card my-agent --tasks "task1,task2"
```

### 2. Storage

Cards are stored in two locations:
- **Agent directory**: `agents/my_agent/agent_cards/my_agent.json`
- **Semantic layer**: `services/semantic_layer/layer/mcp_server/agent_cards/my_agent.json`

### 3. Registration

Semantic layer automatically:
1. Scans `agent_cards/` directory on startup
2. Loads and validates each card
3. Creates vector embeddings for search
4. Indexes in Weaviate vector database

### 4. Discovery

Other agents discover cards via:
- **MCP tools**: `tool_find_agent()`, `tool_recommend_agents()`
- **Semantic search**: Vector similarity matching
- **Direct lookup**: By agent ID or name

### 5. Authentication

When agents communicate:
1. Sender signs request with `shared_secret`
2. Receiver validates signature using card's `auth` field
3. Request is accepted or rejected

## Best Practices

### 1. Descriptive Tasks

Use clear, specific task descriptions:

```bash
# Good
--tasks "analyze_customer_data,generate_sales_report,predict_churn"

# Less specific
--tasks "analyze,report,predict"
```

### 2. Detailed Skills

Provide comprehensive skill information:

```json
{
  "id": "analyze_customer_data",
  "name": "Analyze Customer Data",
  "description": "Performs statistical analysis on customer datasets including segmentation, behavior patterns, and trend identification",
  "tags": ["analysis", "customers", "statistics", "segmentation", "trends"],
  "examples": [
    "Analyze customer purchase history",
    "Segment customers by behavior",
    "Identify customer trends"
  ]
}
```

### 3. Accurate Capabilities

Only declare capabilities your agent actually supports:

```json
{
  "capabilities": {
    "streaming": "True",           // If you support SSE
    "pushNotifications": "False",  // If you don't support push
    "stateTransitionHistory": "False"
  }
}
```

### 4. Secure Secrets

- Never commit `shared_secret` to version control
- Rotate secrets periodically in production
- Use environment variables for sensitive deployments

### 5. Version Management

Update version when making breaking changes:

```json
{
  "version": "2.0.0",  // Breaking change
  "metadata": {
    "version": "2.0.0"
  }
}
```

## Troubleshooting

### Card Not Found

**Symptom**: Semantic layer can't find agent

**Solutions**:
1. Check card exists in `services/semantic_layer/layer/mcp_server/agent_cards/`
2. Verify JSON is valid: `cat agent_card.json | jq`
3. Restart semantic layer: `docker-compose restart semantic-layer`

### Authentication Failed

**Symptom**: Agent-to-agent communication rejected

**Solutions**:
1. Verify `shared_secret` matches in both agents
2. Check `key_id` format: `agent://agent_name-default`
3. Ensure card is loaded by receiving agent

### Semantic Search Not Working

**Symptom**: `tool_find_agent()` returns no results

**Solutions**:
1. Check Weaviate is running: `docker-compose ps weaviate`
2. Verify embeddings are created: Check semantic layer logs
3. Ensure task description is descriptive enough
4. Try broader search terms

### Card Validation Errors

**Symptom**: Semantic layer rejects card

**Solutions**:
1. Validate JSON-LD structure
2. Check required fields: `@context`, `@type`, `id`, `name`, `url`
3. Verify `id` format: `agent://agent_name`
4. Ensure `auth` section is complete

## Examples

### Minimal Card

```json
{
  "@context": ["https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"],
  "@type": "Agent",
  "id": "agent://simple_agent",
  "name": "Simple Agent",
  "description": "Basic agent",
  "url": "http://simple-agent:8000",
  "supportedTasks": ["process_request"],
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://simple_agent-default",
    "shared_secret": "SECRET_HERE"
  }
}
```

### Complete Card

See the full structure example at the top of this document.

## See Also

- [Planner + Orchestrator Integration](planner-orchestrator-integration.md)
- [Semantic Layer Guide](extending-semantic-layer.md)
- [A2A Protocol Specification](../agent_protocols.md)
- [CLI Reference - add agent-card](cli-reference.md#add-agent-card)
