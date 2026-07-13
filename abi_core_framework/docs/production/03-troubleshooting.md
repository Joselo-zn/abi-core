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
docker exec <ollama-container> ollama pull qwen2.5:3b
```

Or check which models are available:

```bash
docker exec <ollama-container> ollama list
```

## Slow responses

**Cause:** Model too large for your hardware.

**Fix:** Use a smaller model:

```python
# config.py
LLM_CONFIG = {"provider": "ollama", "model": "qwen2.5:1.5b"}  # Smaller, faster
```

Or check RAM usage: `docker stats`

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
