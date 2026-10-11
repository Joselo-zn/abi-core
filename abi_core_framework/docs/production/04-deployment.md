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
MODEL_NAME=qwen3:latest
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

## Google Cloud Run

Cloud Run has no Docker daemon, so ephemeral agents can't be containers on a shared network. Set `CONTAINER_RUNTIME=cloudrun` on the Builder and the Orchestrator and install `abi-core-ai[gcp]` in both images: each ephemeral becomes its own Cloud Run service (internal ingress, scale 0–1, CPU always allocated), reached at its run.app URL. Variables: [Environment Variables → Ephemeral runtime](../reference/environment-variables.md#ephemeral-runtime).

What changes compared with Docker Compose:

- **Teardown.** A finished ephemeral exits its process, but its Cloud Run service remains (scaled to zero). The Orchestrator registers a scheduled sweep (`@agent.task_schedule`, needs `abi-core-ai[scheduler]`) that deletes ephemeral services older than `EXECUTION_TIMEOUT` + margin.
- **Service URLs.** No Docker DNS: pass every service URL as an environment variable, and write agent cards with `"${VAR:-local default}"` URLs.
- **One port per service.** Only one port receives traffic. For the Orchestrator expose the web interface port — the web interface calls the agent in-process; A2A keeps running inside the container.
- **IAM.** The Builder's service account needs `roles/run.developer` and `roles/iam.serviceAccountUser` on the ephemerals' service account; the Orchestrator's needs permission to list and delete services.

## Production checklist

- [ ] `A2A_VALIDATION_MODE=strict`
- [ ] API keys in environment variables, not in code
- [ ] `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Health checks configured for all services
- [ ] Volumes for persistent data (Weaviate, MinIO, Ollama models)
- [ ] Resource limits set in compose.yaml
- [ ] Backup strategy for Weaviate data and agent cards
- [ ] HTTPS termination in front of web interfaces
- [ ] `SESSION_BACKEND=redis` + `SESSION_REDIS_URL` on the Orchestrator **and the Builder** (the Builder forwards them to every ephemeral agent — without them, multi-file plans run but their files don't integrate; see [Environment Variables](../reference/environment-variables.md))
- [ ] Every service built against the same `abi-core-ai` version (`pip show abi-core-ai` in each container) — ephemeral agents install the latest at startup, so a stale Orchestrator/Builder image means mixed versions in the same plan
- [ ] `.gitignore` excludes `.env`, credentials/service-account JSON, `__pycache__/` and runtime data (`logs/`, `workspace/`) before pushing to a remote or CI

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

👉 [Artifact Store](05-artifact-store.md)
