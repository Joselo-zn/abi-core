# Environment Variables

All variables are set in `compose.yaml` per service. Agents read them via `config/config.py`.

## Agent configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `qwen3:latest` | LLM model name |
| `OLLAMA_HOST` | `http://<project>-ollama:11434` | Ollama server URL |
| `LLM_PROVIDER` | `ollama` | Provider: ollama, openai, gemini, grok, anthropic, bedrock, azure, vertex |
| `LLM_API_KEY` | — | API key for cloud providers |
| `LLM_TEMPERATURE` | unset (provider default) | LLM temperature. Leave it unset for Claude Opus 4.7+ and Sonnet 5+, which reject `temperature`/`top_p`/`top_k` with an HTTP 400 (Sonnet 5.5 rejects any non-default value). Set it only for providers/models that still honor it. |
| `LLM_BASE_URL` | Ollama: `OLLAMA_HOST`; hosted providers: none | Custom endpoint (gateway, self-hosted). Without it a hosted provider gets no `base_url` — never the Ollama server's |
| `LLM_EXTRA_PARAMS` | — | JSON object passed as-is to the LangChain chat model, for anything provider- or model-specific: `{"thinking_level": "low"}`, `{"max_tokens": 8192}`, `{"thinking": {"type": "adaptive"}}`, `{"api_version": "2024-10-01"}` (Azure). Goes over the agent's own defaults (on Ollama the Orchestrator and ephemerals default to `{"reasoning": false}`), so `{"reasoning": true}` turns qwen3's thinking back on. Invalid JSON, or JSON that isn't an object, stops the agent at start-up with an error naming the variable |
| `AGENT_PORT` | auto-assigned | A2A protocol port |
| `WEB_INTERFACE_PORT` | auto-assigned | HTTP/SSE port (if web interface enabled) |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `ABI_REASONING_TIMEOUT` | `180` | Seconds a single reasoning turn (routing decision, planner call, synthesis) may run before the agent gives up and reports a timeout to the user |
| `ABI_DAG_MAX_WAIT` | `900` | Seconds a full DAG execution (tool-calling pipeline) may run before giving up — separate and more generous than `ABI_REASONING_TIMEOUT` because a DAG step can itself be a slow LLM tool-calling call. See [Troubleshooting → Timeout reported but the work finished anyway](../production/03-troubleshooting.md#timeout-reported-but-the-work-finished-anyway). |
| `EXECUTION_TIMEOUT` | `3600` | Ephemeral agents only — a last-resort backstop, not the mechanism that decides "too slow". Work is bounded by real progress instead: once a model stream starts, 120s without a token counts as a stall; the wait for the *first* token has no limit, since on a single-slot model server a request can legitimately queue behind others. See [Troubleshooting → Timeout reported but the work finished anyway](../production/03-troubleshooting.md#timeout-reported-but-the-work-finished-anyway). |

## Semantic Layer

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMANTIC_LAYER_HOST` | `http://<project>-semantic-layer:10100` | Semantic Layer URL |
| `MCP_HOST` | `<project>-semantic-layer` | MCP server hostname |
| `MCP_PORT` | `10100` | MCP server port |
| `MCP_TRANSPORT` | `streamable-http` | How agents reach the Semantic Layer: `streamable-http`, or `sse` (deprecated, compatibility only). Must match `SEMANTIC_LAYER_TRANSPORT` — see [MCP Transports](mcp-transports.md) |
| `SEMANTIC_LAYER_TRANSPORT` | `streamable-http` | Set on the Semantic Layer: the transport its MCP server speaks |
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
| `PROJECT_RETENTION_DAYS` | `30` | Days before a plan run's files in the bucket expire (bucket lifecycle rule) |
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
| `SESSION_TTL` | `3600` | Idle timeout in seconds — resets on every use (sliding window), not a fixed deadline from creation. See [Sessions & Multi-turn → Token expiry](../single-agent/07-sessions-multi-turn.md#token-expiry-is-a-sliding-window-not-a-fixed-deadline). |
| `SESSION_REDIS_URL` | falls back to `REDIS_URL`, then `redis://localhost:6379/0` | Redis URL for the `redis` backend |
| `ABI_SESSION_REQUIRED` | `false` | If `true`, the orchestrator rejects `/stream` requests without a valid token, and a generated agent's Open WebUI routes (`/api/chat`, `/api/generate`) reject requests without a verified Open WebUI identity or a valid token |
| `OPENWEBUI_JWT_SECRET` | — | On an agent used from Open WebUI: the same value as Open WebUI's `FORWARD_USER_INFO_HEADER_JWT_SECRET` (with `ENABLE_FORWARD_USER_INFO_HEADERS=true`). The agent verifies the user JWT Open WebUI sends and keeps one session per user and chat. An identity that does not verify is rejected (401), never treated as anonymous; the unsigned user-id header is never trusted |
| `CONVERSATION_WINDOW` | `100` | Orchestrator only — how many recent turns stay in the session's conversation window before the oldest is promoted to long-term memory (AMS). The window is also shown to the routing decision as `[SYSTEM STATE] Recent conversation`, so a long window means a long history in every routing prompt. |

> **Multi-pod?** Use `SESSION_BACKEND=redis`. With `memory`, each replica keeps
> its own sessions in RAM, so a request that lands on another pod loses the
> conversation. Redis shares the state across pods.

> **Set them on the Builder too.** The Builder forwards `SESSION_BACKEND` and
> `SESSION_REDIS_URL` to every ephemeral agent it creates. Ephemerals read the
> plan and what the tasks before them produced from this backend (see
> [Dependency Management → What a dependent task receives](../orchestration/03-dependency-management.md#what-a-dependent-task-receives)).
> If the Builder doesn't have them, ephemerals fall back to `memory` and work
> without that context — multi-file plans still run, but the files don't integrate.

## Chainlit UI Authentication (OAuth + invites)

```{note}
**Alpha.** Only set these on the Chainlit UI service (`chatui`), not the
agents themselves. See [Authentication & Invites](../production/07-authentication.md).
```

Unset (default), the bundled Chainlit UI runs anonymous — no login, no
persisted thread history. Setting `OAUTH_GOOGLE_CLIENT_ID` turns on Google
login, a Postgres-backed data layer (persisted conversations, resumable
across logins/devices), and an invite-only registration system.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | Postgres connection string (`postgresql+asyncpg://user:pass@host/db`) for the data layer and the invite/waiting-list tables. Required for any of this section to activate. |
| `OAUTH_GOOGLE_CLIENT_ID` | — | Google OAuth client id. Login only activates once this is set. |
| `OAUTH_GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret. |
| `CHAINLIT_URL` | request's own URL | Chainlit's own var (not ABI-Core's) — the public URL it uses to build the OAuth `redirect_uri` (`<CHAINLIT_URL>/auth/oauth/google/callback`). Must match an Authorized redirect URI on the Google OAuth client. Set explicitly behind a proxy (e.g. Cloud Run) where the request's own URL isn't the public one. |
| `CHAINLIT_AUTH_SECRET` | — | Signs session JWTs. Generate with `chainlit create-secret`. Changing it logs out every active session. |
| `ARTIFACT_ENDPOINT` / `ARTIFACT_ACCESS_KEY` / `ARTIFACT_SECRET_KEY` | — | Same MinIO instance as the [Artifact Store](#artifact-store-minio) — reused so thread elements/files (images, attachments) don't error with "No blob_storage_client is configured". |
| `CHAINLIT_ELEMENTS_BUCKET` | `abi-chainlit-elements` | Separate MinIO bucket from `ARTIFACT_BUCKET` — chat thread elements don't mix with agent-generated artifacts. Create it before first use (`mc mb`). |
| `ADMIN_NOTIFICATION_EMAIL` | — | Where the "someone joined the waiting list" email goes. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | `SMTP_PORT` defaults to `587` | SMTP for the waiting-list notification. Left unset, waiting-list signups still work (recorded in Postgres) — the email is just skipped, logged as a warning. |

## Ollama control

| Variable | Default | Description |
|----------|---------|-------------|
| `START_OLLAMA` | `false` | Start local Ollama in container (distributed mode) |
| `LOAD_MODELS` | `false` | Pull models on container start |

## Ephemeral LLM provider

Set on the **Builder**. Ephemerals can use a different provider than the rest of the swarm (e.g. Ollama for the agents, Gemini for ephemerals).

| Variable | Default | Description |
|----------|---------|-------------|
| `EPHEMERAL_LLM_PROVIDER` | `LLM_PROVIDER` | Provider of the ephemerals (`ollama`, `gemini`, `openai`, `anthropic`, `grok`, `bedrock`, `vertex`). For a hosted provider the ephemeral installs `abi-core-ai[<provider>]` at start-up and receives the API key |
| `EPHEMERAL_MODEL_NAME` | `MODEL_NAME` | Model of the ephemerals, e.g. `gemini-3.6-flash` |
| `EPHEMERAL_LLM_API_KEY` | `LLM_API_KEY` | Key passed to ephemerals for a hosted provider. Use a dedicated, rate-limited key: ephemerals still have `run_shell` and network access, so generated code could read it |
| `EPHEMERAL_LLM_BASE_URL` | — | Custom endpoint for the ephemerals' provider (only passed when set) |
| `EPHEMERAL_LLM_EXTRA_PARAMS` | `LLM_EXTRA_PARAMS`, only if the ephemerals use the Builder's provider | JSON object passed to each ephemeral as its `LLM_EXTRA_PARAMS`, e.g. `{"thinking_level": "low"}` for Gemini ephemerals. A task's own `builder_spec["llm_config"]` goes on top: its `extra_params` win, and its `temperature` becomes the ephemeral's `LLM_TEMPERATURE` |

## Ephemeral runtime

Where the Builder runs ephemeral agents. Set on the **Builder** (spawns) and the **Orchestrator** (tears down / sweeps).

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTAINER_RUNTIME` | `docker` | `docker`: containers on the shared Docker network via `/var/run/docker.sock`. `cloudrun`: one Cloud Run service per ephemeral (requires `pip install "abi-core-ai[gcp]"`) |
| `EPHEMERAL_HEALTH_TIMEOUT` | `300` | Seconds the Builder waits for a new ephemeral's `/health` (start-up includes a `pip install`, measured up to ~70 s). With Docker the wait ends as soon as the container exits, so a broken start-up still fails fast. An ephemeral that never gets healthy is destroyed |
| `CLOUDRUN_PROJECT` | — | GCP project id (required with `cloudrun`) |
| `CLOUDRUN_PROJECT_NUMBER` | — | GCP project number — ephemeral URLs are `https://<service>-<number>.<region>.run.app`, known before the service exists (required with `cloudrun`) |
| `CLOUDRUN_REGION` | — | e.g. `us-central1` (required with `cloudrun`) |
| `CLOUDRUN_SERVICE_ACCOUNT` | project default | Identity ephemerals run as. Give it no Cloud Run permissions: ephemerals run generated code |
| `CLOUDRUN_NETWORK` / `CLOUDRUN_SUBNET` | — | Direct VPC egress for ephemerals, so their calls to other internal services count as internal traffic |
| `ABI_ENV` | `default` | Environment label on every ephemeral service (`alpha`, `prod`); the sweep only deletes its own environment's |
| `EPHEMERAL_CPU` / `EPHEMERAL_MEMORY` | `2` / `4Gi` | Cloud Run limits per ephemeral |
| `EPHEMERAL_REQUEST_TIMEOUT` | `3600` | Cloud Run request timeout (max 3600) — keep it ≥ `EXECUTION_TIMEOUT` |
| `EPHEMERAL_SWEEP_INTERVAL_MINUTES` | `15` | Orchestrator, `cloudrun` only: how often finished/orphaned ephemeral services are deleted |
| `EPHEMERAL_SWEEP_MARGIN_SECONDS` | `600` | The sweep deletes ephemerals older than `EXECUTION_TIMEOUT` + this margin — never one that may still be working |

The Builder also forwards `OPA_URL` and `GUARDIAN_URL` from its own environment (when set), so ephemerals can validate their A2A calls. Without them, an ephemeral in `strict` mode denies every call it makes.

## Result review (ABI Swarm)

Set on the Orchestrator. See [Multi-Agent Workflows → What ABI Swarm adds on top](../orchestration/02-multi-agent-workflows.md#what-abi-swarm-adds-on-top).

| Variable | Default | Description |
|----------|---------|-------------|
| `INTEGRATION_REVIEW` | `true` | Review a plan's code deliverables as a whole before answering |
| `INTEGRATION_REVIEW_SANDBOX` | `true` | Also run them in the [code execution sandbox](../production/08-sandbox.md); `false` keeps only the static checks |

## Code execution sandbox

Set on the process that calls `run_in_sandbox` (the Orchestrator). See [Code Execution Sandbox](../production/08-sandbox.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_RUNTIME` | `docker` | Sandbox backend: `docker` (local Docker socket) or `service` (governed sandbox-service) |
| `SANDBOX_SERVICE_URL` | — | sandbox-service URL, with `SANDBOX_RUNTIME=service` |
| `SANDBOX_IMAGE_PYTHON` | `abi-sandbox-python:latest` | Image for plain Python deliverables |
| `SANDBOX_IMAGE_PYGAME` | `abi-sandbox-pygame:latest` | Image for pygame deliverables |
| `SANDBOX_DOCKER_RUNTIME` | — | Docker runtime for sandboxes, e.g. `runsc` (gVisor) if installed |

On **sandbox-service** itself:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `11500` | Listening port |
| `OPA_URL` | — | OPA server; unset or unreachable means every run is denied |
| `SANDBOX_OPA_PATH` | `abi/sandbox` | OPA data path queried for the decision |
| `SANDBOX_SERVICE_CARD` | `/app/service_cards/sandbox.json` | The service's own `ServiceCard`, used to verify who is calling |
| `SANDBOX_MAX_SKEW_S` | `120` | Maximum age of a request signature, in seconds |

## Agent card

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CARD` | `./agent_cards/<name>_agent.json` | Path to agent card file |

A card's `"url"` may reference the environment: `"${PLANNER_URL:-http://my-planner:11437}"` resolves to `PLANNER_URL` when set, otherwise to the default. One card file then works locally (Docker DNS) and on Cloud Run (the deploy injects the run.app URL). Expanded by `load_agent_card` and by the semantic layer when it indexes cards.
