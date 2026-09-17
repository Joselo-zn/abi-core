# Environment Variables

All variables are set in `compose.yaml` per service. Agents read them via `config/config.py`.

## Agent configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `qwen3:latest` | LLM model name |
| `OLLAMA_HOST` | `http://<project>-ollama:11434` | Ollama server URL |
| `LLM_PROVIDER` | `ollama` | Provider: ollama, openai, gemini, grok, anthropic, bedrock, azure, vertex |
| `LLM_API_KEY` | — | API key for cloud providers |
| `LLM_TEMPERATURE` | unset (provider default) | LLM temperature. Leave unset for models where the provider must pick it — e.g. Claude 4.7+ rejects any explicit `temperature`/`top_p`/`top_k` outright (HTTP 400), unconditionally, not just with extended thinking. Set explicitly only for providers/models that still honor it. |
| `AGENT_PORT` | auto-assigned | A2A protocol port |
| `WEB_INTERFACE_PORT` | auto-assigned | HTTP/SSE port (if web interface enabled) |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `ABI_REASONING_TIMEOUT` | `180` | Seconds a single reasoning turn (routing decision, planner call, synthesis) may run before the agent gives up and reports a timeout to the user |
| `ABI_DAG_MAX_WAIT` | `900` | Seconds a full DAG execution (tool-calling pipeline) may run before giving up — separate and more generous than `ABI_REASONING_TIMEOUT` because a DAG step can itself be a slow LLM tool-calling call. See [Troubleshooting → Timeout reported but the work finished anyway](../production/03-troubleshooting.md#timeout-reported-but-the-work-finished-anyway). |

## Semantic Layer

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMANTIC_LAYER_HOST` | `http://<project>-semantic-layer:10100` | Semantic Layer URL |
| `MCP_HOST` | `<project>-semantic-layer` | MCP server hostname |
| `MCP_PORT` | `10100` | MCP server port |
| `MCP_TRANSPORT` | `streamable-http` | Transport: streamable-http, sse |
| `WEAVIATE_URL` | `http://<project>-weaviate:8080` | Weaviate URL |
| `EMBEDDING_MODEL` | `nomic-embed-text:v1.5` | Model for generating embeddings |

## Security

| Variable | Default | Description |
|----------|---------|-------------|
| `GUARDIAN_URL` | `http://<project>-guardian:11438` | Guardian service URL |
| `OPA_URL` | `http://<project>-opa:8181` | OPA policy engine URL |
| `A2A_VALIDATION_MODE` | `permissive` | strict, permissive, or disabled |
| `A2A_ENABLE_AUDIT_LOG` | `true` | Log all A2A validation attempts |
| `MAX_RISK_THRESHOLD` | `0.7` | Block requests above this risk score |
| `VALIDATION_MODE` | `permissive` | Semantic Layer validation mode |
| `REQUIRE_USER_VALIDATION` | `false` | Require user email for MCP calls |

## Artifact Store (MinIO)

| Variable | Default | Description |
|----------|---------|-------------|
| `ARTIFACT_ENDPOINT` | `http://<project>-minio:9000` | MinIO URL used for internal I/O (upload/download between services) — an in-Docker-network address, not reachable from a browser |
| `ARTIFACT_PUBLIC_ENDPOINT` | falls back to `ARTIFACT_ENDPOINT` | MinIO URL used **only** when generating a presigned download link for a human (e.g. a link in a chat response). Set this to whatever host the user's browser can actually reach — `http://localhost:9000` in local dev, or your real public hostname/reverse-proxy in production. Must be the S3 API endpoint (same port as `ARTIFACT_ENDPOINT`, typically 9000) — MinIO's Console UI port (9001) does not validate presigned URLs, it just serves the Console's own app shell. |
| `ARTIFACT_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `ARTIFACT_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `ARTIFACT_BUCKET` | `abi-artifacts` | Default bucket |
| `LOG_TO_ARTIFACT_STORE` | `true` | Upload execution logs to MinIO |
| `LOG_AGENT_NAME` | agent name | Identifier in log bucket |
| `LOG_BUCKET` | `abi-logs` | Bucket for logs |

## Agent Memory (Redis AMS)

```{note}
**Alpha.** The Agent Memory Server integration is under active development. These
variables may change between releases.
```

`abi-core add service agent-memory` provisions a Redis 8 instance and a Redis Agent
Memory Server (AMS) for system-wide short-term (working) and long-term memory.
Agents reach it over the Docker network.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_URL` | `http://<project>-agent-memory:8000` | AMS base URL (consumed by agents/ephemerals) |
| `CONTEXT_ID` | — | Session/context id used as the AMS `session_id` |

AMS service configuration (set on the `<project>-agent-memory` service in `compose.yaml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://<project>-redis-stack:6379` | Redis 8 backing store |
| `DISABLE_AUTH` | `true` | Disable auth (local/dev only) |
| `LONG_TERM_MEMORY` | `true` | Enable long-term (vector) memory |
| `GENERATION_MODEL` | `ollama/qwen3:latest` | LLM for summarization/extraction (via LiteLLM) |
| `FAST_MODEL` | `ollama/qwen3:latest` | Model for topic extraction / NER |
| `SLOW_MODEL` | `ollama/qwen3:latest` | Model for complex tasks |
| `EMBEDDING_MODEL` | `ollama/nomic-embed-text:v1.5` | Embedding model (768 dims) |
| `OLLAMA_API_BASE` | `http://ollama:11434` | Ollama endpoint for LiteLLM |
| `REDISVL_VECTOR_DIMENSIONS` | `768` | Vector dimensions (must match embedding model) |

> **Note:** AMS requires **Redis 8+** because it uses the `HSETEX` command (introduced
> in Redis 8.0). Redis 8 also bundles RediSearch/RedisJSON in the core, so the
> `redis:8` image is sufficient — no separate `redis-stack` modules needed.

## Async Task Backend

```{note}
**Alpha.** `@agent.task_async`/`@agent.task_schedule` are under active
development. These variables may change between releases.
```

Where `agent.get_async_task_status(...)` looks up a background/scheduled task's
status, and where `overlap_policy="skip"` checks "is the previous firing still
running?" — see [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `ASYNC_TASK_BACKEND` | `memory` | `memory` (per-pod, in-process) or `redis` (shared, multi-pod safe) |

> **Multi-pod?** Same story as sessions: with `memory`, each replica only sees its
> own background tasks, so an overlap check can miss a firing on another pod.
> Use `ASYNC_TASK_BACKEND=redis` — it reuses `REDIS_URL`, no new infra to stand up
> if you've already got `abi-core add service agent-memory` running.

## Session Management

```{note}
**Alpha.** Framework-managed sessions are under active development. These
variables may change between releases.
```

Sessions tie an opaque token to an internal `context_id` and its conversation
context. The backend is pluggable: `memory` (per-pod, dev) or `redis` (shared
state, LB/multi-pod safe). See [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_BACKEND` | `memory` | `memory` (per-pod, in-process) or `redis` (shared, multi-pod safe) |
| `SESSION_TTL` | `3600` | Session/context lifetime in seconds |
| `SESSION_REDIS_URL` | falls back to `REDIS_URL`, then `redis://localhost:6379/0` | Redis URL for the `redis` backend |
| `ABI_SESSION_REQUIRED` | `false` | If `true`, the orchestrator rejects `/stream` requests without a valid token |

> **Multi-pod?** Use `SESSION_BACKEND=redis`. With `memory`, each replica keeps
> its own sessions in RAM, so a request that lands on another pod loses the
> conversation. Redis shares the state across pods.

## Ollama control

| Variable | Default | Description |
|----------|---------|-------------|
| `START_OLLAMA` | `false` | Start local Ollama in container (distributed mode) |
| `LOAD_MODELS` | `false` | Pull models on container start |

## Agent card

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CARD` | `./agent_cards/<name>_agent.json` | Path to agent card file |
