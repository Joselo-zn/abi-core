# Sessions & Multi-turn

```{note}
**Alpha.** Framework-managed sessions are under active development. The API and
environment variables may change between releases.
```

A **session** ties an opaque token to an internal `context_id` and the
conversation context accumulated for it. Sessions are what make multi-turn
conversations reliable — a clarification question in turn 1 and its answer in
turn 2 land in the same context, even behind a load balancer.

Sessions are **opt-in** and **generic**: any agent built on ABI-Core gets them,
whether or not it uses the reference orchestrator/swarm.

## Why sessions (and why not client-supplied ids)

Before sessions, clients sent their own `context_id` in the request body. That
has two problems:

1. **Spoofing / collision** — anyone can send any id. If everyone defaults to
   `"web-session"`, all users share one context and step on each other.
2. **Per-pod state** — the conversation context lived in the agent process's
   RAM. Behind a load balancer with several replicas, turn 2 can land on a
   different pod that never saw turn 1. The session breaks.

Framework sessions fix both: the `context_id` is generated in the **backend**
(opaque, never trusted from the client), and the context lives in a **shared
backend** instead of process RAM.

```{note}
This is the *local vs global* principle: state that must survive a pod belongs
to the **system** (a shared store), never to a single agent's process memory.
```

## The two backends

| Backend | State lives in | Use for | LB / multi-pod safe |
|---------|----------------|---------|:---:|
| `memory` (default) | The agent process (a dict) | Dev, a single-pod agent | ❌ |
| `redis` | Shared Redis | Production, multiple replicas | ✅ |

You pick the backend with an environment variable — **your agent code does not
change**:

```bash
# Development (default): per-pod, in-memory
SESSION_BACKEND=memory

# Production: shared state, survives pod hops
SESSION_BACKEND=redis
SESSION_REDIS_URL=redis://my-project-redis:6379/0   # falls back to REDIS_URL
```

See [Environment Variables](../reference/environment-variables.md#session-management)
for the full list.

## Using sessions over HTTP

If your agent has a web interface, session endpoints are wired up for you. Start
a session, then send its token as a bearer token on each request.

```bash
# 1. Start a session — the backend returns an opaque token
curl -X POST http://localhost:8000/session/start
# → {"session_token": "abi_sess_7f3a…b2c1", "expires_at": 1780000000.0}

# 2. Use the token on every request. The backend resolves it to a context_id;
#    the body no longer needs (or can spoof) a context_id.
curl -X POST http://localhost:8000/stream \
  -H "Authorization: Bearer abi_sess_7f3a…b2c1" \
  -H "Content-Type: application/json" \
  -d '{"query": "create a python pong game"}'

# 3. A follow-up in the SAME session (same token) shares the context —
#    e.g. answering a clarification from the previous turn.
curl -X POST http://localhost:8000/stream \
  -H "Authorization: Bearer abi_sess_7f3a…b2c1" \
  -d '{"query": "q1: use pygame"}'
```

### Session endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/session/start` | POST | Create a session; returns `session_token` + `expires_at` |
| `/session/rotate` | POST | Issue a new token for the same session (invalidates the old one) |
| `/session/end` | POST | Destroy the session and its context |
| `/stream`, `/query` | POST | Send `Authorization: Bearer <token>` to keep a stable session |

### No token? Anonymous sessions

If a request arrives without a valid token, the web interface creates a
short-lived **anonymous** session in the same backend, so each caller still gets
a unique, isolated `context_id` (no shared `web-session` collision). Set
`ABI_SESSION_REQUIRED=true` to reject tokenless requests on the orchestrator
instead.

## Using sessions in code

The same capability is available programmatically via `SessionStore`:

```python
from abi_core.agent import SessionStore

store = SessionStore.from_env()          # picks the backend from SESSION_BACKEND

session = await store.create_session(metadata={"user": "alice"})
token = session.tokens[0]                # opaque: "abi_sess_…"

# Later, resolve a token back to its session (any pod, with the redis backend)
resolved = await store.resolve(token)
context_id = resolved.context_id

# Read / update the conversation context (keyed by context_id)
await store.update_context(context_id, {"last_step": "planning"})
ctx = await store.get_context(context_id)   # {"last_step": "planning"}

# Lifecycle
new_token = await store.rotate(token)    # old token now invalid, context kept
await store.destroy(new_token)           # session + context gone
```

### Inside an agent

`AbiAgent` owns a `session_backend` and exposes async helpers. The default is
in-memory; inject a backend (or set `SESSION_BACKEND=redis`) for multi-pod:

```python
from abi_core.agent import AbiAgent, RedisSessionBackend

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="...",
            llm_config=config.LLM_CONFIG,
            # Optional — defaults to the backend from SESSION_BACKEND.
            session_backend=RedisSessionBackend("redis://my-project-redis:6379/0"),
        )

    async def stream(self, query, context_id, task_id):
        # Detects "id: text" answers and merges them into the session context
        context, was_answer = await self.process_answer(context_id, query)
        # Read / write session context directly
        await self.update_session_context(context_id, {"seen": True})
        ...
```

## Concurrency & latency (know the trade-offs)

- **Concurrency.** Two requests for the same session hitting two pods can race on
  the shared context. With the Redis backend, each context field is written
  independently, so updates to *different* keys don't clobber each other; a
  read-modify-write of the *same* field is last-writer-wins. That's fine for
  turn-scoped state — don't use it as a transactional store.
- **Latency.** With Redis, each request does a small round-trip to resolve the
  token and read context. That's the cost of being stateless — and it's what
  lets any pod serve any turn. Sticky sessions (LB affinity by token) are an
  optional optimization, **not** a substitute for shared state.
- **Graceful degradation.** If the backend is unreachable, session calls log a
  warning and return safe defaults instead of raising, so a store hiccup never
  crashes a request.

## Next step

👉 [Testing Agents](05-testing-agents.md)
