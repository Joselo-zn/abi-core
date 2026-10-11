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

## Log lines worth knowing (Orchestrator)

The lines that answer "what did the system decide, and why":

| Where | Line | What it tells you |
|-------|------|-------------------|
| Orchestrator | `[🚦] Gate decision: action=...` | Deterministic routing (plan confirmation, clarification answer) or handoff to the LLM reasoning turn |
| Orchestrator | `[🧭] Routing decision: action=... valid=[...] history_turns=N detail='...'` | What the LLM chose in the reasoning turn (`create_plan`, `answer_directly`, ...), the options it had, and how much conversation history it saw |
| Orchestrator | `[🔨] Creating workflow with N tasks` | The approved plan is being turned into running agents |
| Ephemeral | `[🔑] Session backend: redis (...)` | The ephemeral shares the Orchestrator's session store (required for tasks to build on each other) |

## Artifact Store logs

If `LOG_TO_ARTIFACT_STORE=true`, agent execution logs are uploaded to MinIO for long-term storage:

```yaml
environment:
  - LOG_TO_ARTIFACT_STORE=true
  - LOG_AGENT_NAME=orchestrator
  - LOG_BUCKET=abi-logs
```

Access via MinIO console: `http://localhost:9001`

## Security decisions

Guardian doesn't expose a metrics endpoint. Every allow/deny decision is written to the logs — see [Audit & Compliance](../security/05-audit-compliance.md):

```bash
docker compose logs -f <project>-guardian
```

## Next step

👉 [Troubleshooting](03-troubleshooting.md)
