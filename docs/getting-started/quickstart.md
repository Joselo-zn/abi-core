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

## Add an Agent

```bash
# Create a specialized agent
abi-core add agent assistant --description "AI assistant agent"
```

## Start the System

```bash
# Start all services (if not already running)
docker-compose up -d

# View logs
docker-compose logs -f
```

## Test Your Agent

```bash
# Query the agent via HTTP
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello, how can you help me?","context_id":"test","task_id":"task-001"}'
```

## Project Structure

Your project now has:

```
my-ai-system/
├── agents/
│   └── assistant/
│       ├── main.py
│       ├── assistant.py
│       └── agent_cards/
├── services/
│   └── semantic_layer/
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

# Check project status
abi-core status

# List all agents
abi-core info agents

# Add another agent
abi-core add agent analyzer --description "Data analyzer"

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
