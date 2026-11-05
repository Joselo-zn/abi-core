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
curl http://localhost:11438/health  # Guardian (see the note in Guardian Service for older projects)
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

abi_logging("[✅] Step completed")
abi_logging("[❌] Error: ...")
```

### Never log what the user wrote

Logs end up in places users never agreed to share their messages with: container logs, a log collector, the artifact store. So anything that comes from the user, or is built from it — the message, a plan, a prompt, the model's output, tool arguments, generated code — goes into a log line through `redact()`, never directly:

```python
from abi_core.common.utils import abi_logging, redact, mask_email

abi_logging(f"[📥] Query: {redact(query)}")
# [📥] Query: <text len=50 sha=4bb686a0>

abi_logging(f"[👤] User: {mask_email(email)}")
# [👤] User: j***@example.com
```

`redact()` logs a fingerprint — the length and a short hash — instead of the content. It accepts a string or anything JSON-serializable (`None` gives `<none>`), and the same text always gives the same fingerprint, so you can follow one message across agents and retries without reading it. `mask_email()` keeps the first letter and the domain (`<redacted>` if there's no `@`).

ABI's own log lines already work this way. To see the content while debugging on your machine, set `ABI_LOG_USER_CONTENT=true`: `redact()` and `mask_email()` then return their input unchanged. Never set it anywhere real users are.

## Log lines worth knowing (Orchestrator)

The lines that answer "what did the system decide, and why":

| Where | Line | What it tells you |
|-------|------|-------------------|
| Orchestrator | `[🚦] Gate decision: action=...` | Deterministic routing (plan confirmation, clarification answer) or handoff to the LLM reasoning turn |
| Orchestrator | `[🧭] Routing decision: action=... valid=[...] history_turns=N detail='...'` | What the LLM chose in the reasoning turn (`create_plan`, `answer_directly`, ...), the options it had, and how much conversation history it saw |
| Orchestrator | `[🔨] Creating workflow with N tasks` | The approved plan is being turned into running agents |
| Ephemeral | `[🔑] Session backend: redis (...)` | The ephemeral shares the Orchestrator's session store (required for tasks to build on each other) |

## Artifact Store logs

If `LOG_TO_ARTIFACT_STORE=true` (default `false`), agent execution logs are uploaded to MinIO for long-term storage — one more reason to keep user content out of them:

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
