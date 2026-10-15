# Troubleshooting

Common problems and how to fix them.

## Agent not responding

```bash
# Is it running?
docker compose ps

# What's in the logs?
docker compose logs --tail=50 my-agent

# Restart it
docker compose restart my-agent
```

## "Model not found"

The LLM model isn't pulled yet:

```bash
docker exec <ollama-container> ollama pull qwen3:latest
```

Or check which models are available:

```bash
docker exec <ollama-container> ollama list
```

## Slow responses

**Cause:** Model too large for your hardware.

**Fix:** Use a smaller model:

```bash
docker exec ollama ollama pull qwen3:1.7b
```

Then set `MODEL_NAME=qwen3:1.7b` on the agent in `compose.yaml` and restart it (`docker compose up -d <agent>`).

Or check RAM usage: `docker stats`

If a specific step consistently needs more time than the default budget
(`ABI_REASONING_TIMEOUT`, 180s for a single reasoning turn; `ABI_DAG_MAX_WAIT`,
900s for a full DAG) rather than being genuinely stuck, raise the relevant one
instead of just switching models — see
[Environment Variables → Agent configuration](../reference/environment-variables.md#agent-configuration).

## Timeout reported but the work finished anyway

Symptoms: the user gets "This is taking longer than expected (over Ns); the
model is probably overloaded. Try again." — or its Spanish version in the
Chainlit UI — but the file/container/side effect the request was supposed to
produce shows up moments later anyway.

**Cause:** this isn't a bug in the timeout message — it's a real limit of how
Python's asyncio cancellation works. When a timeout fires, the framework asks
the in-flight work to cancel, but that's a cooperative request, not a kill
switch. If the actual work at that moment is a synchronous call running in a
background thread (e.g. the Docker SDK calls in ephemeral-agent lifecycle
management), cancelling the `asyncio` task that's waiting on it does **not**
stop the thread — Python has no way to force-kill a running thread. The
thread keeps going and can still complete the operation after the user has
already been told it timed out.

**What to do:** treat the timeout message as "the framework stopped waiting",
not as "the operation was undone". Check whether the expected result (file,
container, artifact) actually appeared before retrying — a retry on top of
one that quietly succeeded can duplicate work (e.g. a second container with
the same effect). If this happens often for the same operation, it usually
means its timeout budget is too tight for what it actually costs (see
"Slow responses" above), not that something is broken.

## Ephemeral agent step is slow under concurrent load — is that a timeout risk?

Symptoms: several plan tasks run in parallel, all hitting the same LLM
backend at once, and one ephemeral agent genuinely takes several minutes
because it's queued behind the others — not stuck.

**This is not a timeout risk by design.** `EXECUTION_TIMEOUT`
(default 3600s) is a last-resort backstop, not the mechanism deciding
"this took too long" — the real bounding happens at the point of actual
work:

- The LLM stream is read **token by token** (`stream_mode="messages"`).
  Once tokens start arriving, 120s with none is treated as a stall. The wait
  for the *first* token has no limit of its own: with a single-slot model
  server (Ollama runs with one generation slot by default, `-np 1`), a
  request queued behind another generation legitimately sees nothing until
  that slot frees up.
- The memory lookup against AMS has its own 30s timeout.

A task that's genuinely still producing output — just slowly, because it's
queued behind other concurrent work — survives as long as it keeps making
real progress. If the 3600s backstop actually fires, something is genuinely
stuck, not merely slow.

When a step does time out, the error message now carries the real cause and
duration (e.g. `Agent stream stalled twice (120.0s each)...`) instead of a
generic `Node '...' exceeded its 3600.0s timeout` for every timeout.

## Chainlit shows "No response received." while the backend keeps working

Symptoms: a long plan (several ephemeral tasks) shows no progress in the
chat for minutes, then Chainlit gives up with "No response received." —
while the Orchestrator logs and the model server show work still going on.

**Cause (fixed):** the chat client reads the Orchestrator's `/stream` with
a 600s timeout *between* received events. During task execution, progress
from ephemeral agents (a heartbeat every ~15s) used to never reach the
client: the workflow graph collected each task's events and only released
them once the whole task finished, so a task longer than 600s looked dead.
Task progress now streams live (LangGraph `stream_mode=["custom",
"updates"]` in `AgentInteractionFlow.run_workflow`), and heartbeats are
relayed whether they arrive as message text or status text.

**If you still see it:** confirm progress is actually flowing by calling
`/stream` directly — you should see a new `data:` line at least every ~15s
during execution:

```bash
curl -N -X POST http://<orchestrator>:<WEB_INTERFACE_PORT>/stream \
  -H "Content-Type: application/json" -d '{"query": "..."}'
```


## Multi-file deliverable: the files don't use each other

Symptoms: a plan produces several files, but one of them reimplements what
the others already define, or imports modules that don't exist.

Check that every ephemeral agent shares the Orchestrator's session store.
Their logs must show `Session backend: redis`, not `in-memory`. If they show
`in-memory`, set `SESSION_BACKEND`/`SESSION_REDIS_URL` on the **Builder** —
it forwards them to every agent it creates (see
[Environment Variables](../reference/environment-variables.md#session-management)).
Without a shared store, each agent works without knowing what the others
produced.

## The Orchestrator keeps answering instead of making a plan

Symptoms: repeated requests to build something get a conversational reply
("Would you like me to help you create...?") instead of a plan — sometimes
the exact same reply word for word.

Every routing decision is logged:

```
[🧭] Routing decision: action=answer_directly valid=[...] history_turns=11 detail='...'
```

If `history_turns` is high and the replies repeat verbatim, the model is
copying an earlier reply from the conversation history shown to it
(`CONVERSATION_WINDOW`). Workaround: start a new chat (fresh history).

## Semantic Layer not finding agents

Symptoms: `find_agent` returns nothing, orchestrator logs "agent not found" or a
`system_error`, even though the agent container is running and healthy.

```bash
# Are agent cards in the right place? (disk is the source of truth)
ls services/semantic_layer/agent_cards/

# Is Weaviate healthy?
curl http://localhost:8081/v1/.well-known/ready

# Does the Semantic Layer consider itself healthy? (see below)
curl -i http://localhost:10100/health

# Restart to re-index / self-heal
docker compose restart <project>-semantic-layer
```

### Root cause: agent cards stored without vectors

The most common cause is **agent cards indexed without an embedding vector**. A
vectorless object exists in the store (so a plain fetch finds it) but is invisible to
vector search (`near_vector`), so discovery silently returns nothing.

This happens when the Semantic Layer indexes cards **before Ollama can serve the
embedding model** at startup — the embedding call returns empty and, in older
versions, the empty object was persisted and never repaired.

Inspect the stored vectors directly:

```bash
curl -s http://localhost:8081/v1/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ Get { AgentCard(limit:10){ uri _additional{ id vector } } } }"}'
```

If `vector` is `[]` for your cards, that is the problem.

### Self-healing (current versions)

ABI-Core now guards store integrity in several layers, so this repairs itself:

- **Startup** waits until Ollama can actually embed before indexing, and never
  persists a card without a valid vector.
- **On a search miss**, the Semantic Layer reconciles against disk (the source of
  truth): it re-embeds and re-indexes any card that is on disk but not yet vectorized,
  then retries the search. Cards already valid are left untouched.
- **`/health`** returns `503 degraded` when the store has no vectorized cards, so the
  broken state is visible instead of silent.

A `docker compose restart <project>-semantic-layer` triggers re-indexing. If a card
still isn't found afterward, check the logs — they now distinguish the cases:

```bash
docker compose logs --tail=50 <project>-semantic-layer
```

- `re-indexed N card(s) from disk` → it self-repaired.
- `could not be embedded (Ollama unavailable?)` → the embedding model isn't ready;
  pull it / wait and retry (see "Model not found").
- `card is not present on disk (legitimate absence)` → the card simply doesn't exist;
  add its JSON to `services/semantic_layer/agent_cards/`.

## "Port already in use"

Another process is using that port. Either stop it or change the port in `compose.yaml`:

```yaml
ports:
  - "8003:8002"  # Map to a different host port
```

## A2A connection refused

The target agent isn't ready yet. Check:

```bash
# Is the target running?
docker compose ps

# Can you reach it?
curl http://<target-container>:<port>/health
```

Common cause: the agent depends on Semantic Layer which depends on Weaviate. Wait for health checks to pass.

## "Session terminated" from MCP

The Semantic Layer connection dropped. `MCPToolkit.call_with_retry()` handles this automatically:

```python
result = await toolkit.call_with_retry("my_tool", max_retries=3, param="value")
```

## Session is lost between requests

Symptoms: multi-turn breaks — a clarification answer isn't recognized, context
from a previous turn is gone, or every request behaves like a brand-new session.

**Most common cause:** the in-memory session backend behind multiple replicas.
With `SESSION_BACKEND=memory`, each pod keeps its sessions in its own RAM. Behind
a load balancer, turn 2 can land on a different pod that never saw turn 1.

**Fix:** use the shared Redis backend so any pod resolves the same session:

```bash
SESSION_BACKEND=redis
SESSION_REDIS_URL=redis://<project>-redis:6379/0   # falls back to REDIS_URL
```

Other things to check:
- **No token sent.** Without `Authorization: Bearer <token>`, each request gets a
  fresh anonymous session. Call `/session/start` once and reuse the token.
- **Token expired.** Sessions expire after `SESSION_TTL` (default 3600s). Rotate
  or start a new session.
- **Restarted pod with `memory` backend.** In-memory sessions don't survive a
  restart. Use Redis for durability.

See [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md).

## Container keeps restarting

Check logs for the crash reason:

```bash
docker compose logs --tail=100 <container>
```

Common causes:
- Missing environment variable
- Agent card file not found
- Python import error (missing dependency)

## Next step

👉 [Deployment](04-deployment.md)
