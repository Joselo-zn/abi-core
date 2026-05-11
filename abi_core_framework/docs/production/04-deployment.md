# Deployment

Your project is already containerized. Deployment is about where you run those containers.

## Docker Compose (single machine)

The simplest option. Good for small teams and moderate traffic.

```bash
# Start everything
docker compose up -d

# Rebuild after code changes
docker compose up --build -d

# Stop
docker compose down
```

## Environment variables

Create a `.env` file in your project root:

```bash
# LLM
MODEL_NAME=qwen2.5:3b
OLLAMA_HOST=http://ollama:11434

# Cloud LLM (if using)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...

# Security
A2A_VALIDATION_MODE=strict
MAX_RISK_THRESHOLD=0.7

# Logging
LOG_LEVEL=INFO
LOG_TO_ARTIFACT_STORE=true
```

Docker Compose reads `.env` automatically.

## Scale agents

```bash
# Run 3 instances of an agent
docker compose up -d --scale my-agent=3
```

Note: you'll need a load balancer in front if scaling. The Semantic Layer handles discovery — it routes to whichever instance is healthy.

## Docker Swarm (cluster)

For multi-machine deployments:

```bash
docker swarm init
docker stack deploy -c compose.yaml my-system
docker service ls
docker service scale my-system_my-agent=5
```

## Kubernetes

Convert your compose file:

```bash
kompose convert -f compose.yaml
kubectl apply -f .
kubectl get pods
```

## Production checklist

- [ ] `A2A_VALIDATION_MODE=strict`
- [ ] API keys in environment variables, not in code
- [ ] `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Health checks configured for all services
- [ ] Volumes for persistent data (Weaviate, MinIO, Ollama models)
- [ ] Resource limits set in compose.yaml
- [ ] Backup strategy for Weaviate data and agent cards
- [ ] HTTPS termination in front of web interfaces

## Backup

```bash
# Ollama models
docker run --rm -v ollama_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/ollama-backup.tar.gz /data

# Weaviate data
docker run --rm -v weaviate_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/weaviate-backup.tar.gz /data

# Configuration
tar czf config-backup.tar.gz .abi/ services/ agents/
```

## Next step

👉 [CLI Reference](../reference/cli-reference.md)
