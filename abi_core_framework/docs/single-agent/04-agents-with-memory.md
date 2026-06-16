# Agents with Memory

By default, each request is independent — the agent doesn't remember previous messages. Memory fixes that.

## How it works

ABI-Core uses `thread_id` in `invoke()` to maintain conversation history. The LLM sees all previous messages in the same thread.

```python
from abi_core.agent.llm_provider import invoke

# First message
result = await invoke(config.LLM_CONFIG, "My name is Ana", thread_id="session-001")

# Second message — the LLM remembers "Ana"
result = await invoke(config.LLM_CONFIG, "What's my name?", thread_id="session-001")
# → "Your name is Ana"
```

## Add memory to your agent

The key is passing `context_id` as the `thread_id`. Edit your step:

```python
@agent.step(name="chat_with_memory")
async def chat_with_memory(text, context_id):
    """Respond with conversation memory."""
    from abi_core.agent.llm_provider import invoke
    from prompts import CHAT_PROMPT

    result = await invoke(
        config.LLM_CONFIG,
        CHAT_PROMPT.format(text=text),
        thread_id=context_id,  # This enables memory
    )
    return {"response": result}
```

And your task passes the `context_id` through:

```python
@agent.task(name="chat", task_id="task-chat")
async def chat(query):
    data = json.loads(query) if isinstance(query, str) else query
    text = data.get("text", "")
    context_id = data.get("context_id", "default")

    result = await agent.execute_step(
        "chat_with_memory", text=text, context_id=context_id
    )
    yield AgentResponse.result(result)
```

## Test it

```bash
# First message
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "My name is Carlos", "context_id": "session-42"}'

# Second message — same context_id
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is my name?", "context_id": "session-42"}'
# → "Your name is Carlos"
```

## How context_id works

- Same `context_id` = same conversation (agent remembers)
- Different `context_id` = fresh conversation (no memory)
- The web interface generates a `context_id` per session automatically

## Memory is in-process

The default memory (LangGraph `MemorySaver`) lives in the agent's process memory. If the container restarts, memory is lost. For persistent, system-wide memory use the Agent Memory Server (below).

## Persistent memory with the Agent Memory Server (AMS)

```{warning}
**Alpha.** System memory via the Agent Memory Server is part of the ABI Swarm, which
is under active development. Configuration and behavior may change between releases.
```

The two kinds of memory are different:

- **Agent memory** — the conversation thread of a single agent (`thread_id`, in-process). Local and volatile.
- **System memory** — a global store shared across the swarm, persisted in Redis. It captures events that matter to the whole system (e.g. a pending clarification, results of past tasks), survives restarts, and any agent can query it.

The swarm scaffolding (`abi-core create swarm`) provisions system memory automatically with two services:

- `<project>-redis-stack` — Redis 8 (backing store)
- `<project>-agent-memory` — Redis Agent Memory Server (working + long-term memory)

Agents and ephemerals receive `AGENT_MEMORY_URL` and `CONTEXT_ID` as environment variables and reach AMS over the Docker network.

### What AMS provides

| Type | Scope | Use |
|------|-------|-----|
| Working (short-term) memory | Per session (`context_id`) | Current task state, multi-turn context |
| Long-term memory | Persistent, semantic | Past results, preferences, episodes — searched by similarity |

AMS runs fully local through Ollama (via LiteLLM) — no cloud API keys required. See [Environment Variables](../reference/environment-variables.md#agent-memory-redis-ams) for the full configuration.

> **Requires Redis 8+.** AMS uses the `HSETEX` command (Redis 8.0). The `redis:8` image bundles RediSearch/RedisJSON in the core, so it works out of the box.

## Next step

👉 [Built-in Memory API](06-builtin-memory.md)
