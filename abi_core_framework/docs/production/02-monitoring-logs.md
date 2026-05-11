# Monitoring & Logs

How to see what your agents are doing.

## Logs

```bash
# All services
docker compose logs -f

# One agent
docker compose logs -f my-agent

# Last 50 lines
docker compose logs --tail=50 my-agent
```

## Health checks

Every agent and service exposes `/health`:

```bash
curl http://localhost:8002/health   # Agent web interface
curl http://localhost:10100/health  # Semantic Layer
curl http://localhost:11438/health  # Guardian
curl http://localhost:8181/health   # OPA
curl http://localhost:11434/api/tags # Ollama
```

## Service status

```bash
# Container status
docker compose ps

# Resource usage (CPU, RAM)
docker stats
```

## Agent logging in code

Use `abi_logging()` — it writes to stdout (captured by Docker):

```python
from abi_core.common.utils import abi_logging

abi_logging("[📥] Received query: ...")
abi_logging("[✅] Step completed")
abi_logging("[❌] Error: ...")
```

## Artifact Store logs

If `LOG_TO_ARTIFACT_STORE=true`, agent execution logs are uploaded to MinIO for long-term storage:

```yaml
environment:
  - LOG_TO_ARTIFACT_STORE=true
  - LOG_AGENT_NAME=orchestrator
  - LOG_BUCKET=abi-logs
```

Access via MinIO console: `http://localhost:9001`

## Security metrics

```bash
curl http://localhost:11438/v1/tools/get_security_metrics
```

Returns request counts, blocked requests, average risk scores, and active agents.

## Next step

👉 [Troubleshooting](03-troubleshooting.md)
