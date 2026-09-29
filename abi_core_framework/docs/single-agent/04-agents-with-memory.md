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

The two kinds of memory are different:

- **Agent memory** (this page) — the conversation thread of a single agent (`thread_id`, in-process). Local and volatile.
- **Built-in memory API** — a system-wide store any agent can opt into, backed by the Agent Memory Server (AMS) and persisted in Redis. It captures things worth keeping deliberately (a pending clarification, results of past tasks, a user preference), survives restarts, and any agent — not just a swarm's — can query it.

`abi-core add service agent-memory` provisions it with two services (`<project>-redis-stack` + `<project>-agent-memory`) and works for a single agent created with `abi-core add agent` exactly as well as for a multi-agent setup — it is **not** swarm-specific. The full write/read API, the `MEMORY_TOOLS` for LLM-driven recall, and the AMS environment variables are covered on the next page — this section is just the pointer.

## Next step

👉 [Built-in Memory API](06-builtin-memory.md)
