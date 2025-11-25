# Quick Start

Get up and running with ABI-Core in 5 minutes.

## Create Your First Project

```bash
# Create a new project with semantic layer
abi-core create project my-ai-system --with-semantic-layer

# Navigate to your project
cd my-ai-system
```

## Provision Models

```bash
# Automatically start services and download models
abi-core provision-models
```

This command will:
- Start the Ollama service automatically
- Download the LLM model (qwen2.5:3b by default)
- Download the embedding model (nomic-embed-text:v1.5)
- Update runtime.yaml with provisioning status

## Add Orchestration Layer

```bash
# Add Planner and Orchestrator for multi-agent coordination
abi-core add agentic-orchestration-layer
```

This creates:
- **Planner Agent**: Decomposes tasks and assigns agents
- **Orchestrator Agent**: Coordinates workflow execution

## Add Worker Agents

```bash
# Create specialized agents
abi-core add agent assistant --description "AI assistant agent"
abi-core add agent analyzer --description "Data analyzer agent"

# Register agents with semantic layer
abi-core add agent-card assistant \
  --url "http://assistant-agent:8000" \
  --tasks "answer_questions,provide_help"

abi-core add agent-card analyzer \
  --url "http://analyzer-agent:8001" \
  --tasks "analyze_data,generate_insights"
```

## Start the System

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Test Your System

### Test Individual Agent
```bash
# Query an agent directly
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello, how can you help me?","context_id":"test","task_id":"task-001"}'
```

### Test Multi-Agent Workflow
```bash
# Send complex query to Orchestrator
curl -X POST http://localhost:8083/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "analyze customer data and provide recommendations",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

The Orchestrator will:
1. Send query to Planner for task decomposition
2. Planner finds appropriate agents using semantic search
3. Orchestrator executes workflow with assigned agents
4. Results are synthesized and returned

## Project Structure

Your project now has:

```
my-ai-system/
├── agents/
│   ├── planner/              # Task decomposition
│   │   ├── agent/
│   │   └── agent_cards/
│   ├── orchestrator/         # Workflow coordination
│   │   ├── agent/
│   │   └── agent_cards/
│   ├── assistant/            # Worker agent
│   │   └── agent_cards/
│   └── analyzer/             # Worker agent
│       └── agent_cards/
├── services/
│   ├── semantic_layer/       # Agent discovery
│   │   └── layer/mcp_server/agent_cards/
│   └── guardian/             # Security policies
├── compose.yaml
└── .abi/
    └── runtime.yaml
```

## Next Steps

- [Create more agents](../user-guide/agents.md)
- [Configure semantic layer](../user-guide/semantic-layer.md)
- [Add security policies](../user-guide/security.md)
- [Deploy to production](../user-guide/deployment.md)

## Common Commands

```bash
# Provision models (download and configure)
abi-core provision-models

# Add orchestration layer
abi-core add agentic-orchestration-layer

# Check project status
abi-core status

# List all agents
abi-core info agents

# Add another agent
abi-core add agent analyzer --description "Data analyzer"

# Register agent with semantic layer
abi-core add agent-card analyzer \
  --url "http://analyzer-agent:8001" \
  --tasks "analyze_data,generate_report"

# Stop services
docker-compose down
```

## Troubleshooting

### Port Already in Use

If you see port conflicts:

```bash
# Check what's using the port
lsof -i :8000

# Change the port in .abi/runtime.yaml
```

### Model Not Found

Use the provision-models command to download models automatically:

```bash
abi-core provision-models
```

Or manually pull a specific model:

```bash
docker exec my-ai-system-ollama ollama pull qwen2.5:3b
```

### Container Won't Start

Check logs:

```bash
docker-compose logs <service-name>
```
