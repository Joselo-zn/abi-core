# Built-in Memory API

```{note}
**Alpha.** The built-in memory API is backed by the Agent Memory Server (AMS),
provisioned by the ABI Swarm scaffolding. It is under active development and the
API may change between releases.
```

The [previous page](04-agents-with-memory.md) covered **conversation memory** — the LLM remembering messages in a thread. This page covers the **built-in memory API**: explicit functions to store and recall information across steps, tasks, and sessions, backed by the Agent Memory Server (AMS).

## Two kinds of memory

| | Conversation memory (`thread_id`) | Built-in memory API (AMS) |
|---|---|---|
| Scope | One agent's LLM thread | System-wide, shared across agents |
| Persistence | In-process (lost on restart) | Redis-backed (survives restarts) |
| Control | Implicit (LLM sees history) | Explicit (you choose what to store) |
| Types | Conversation only | Short-term + long-term semantic |

Use conversation memory for chat continuity. Use the built-in API when you need to **deliberately** save a result, a decision, or a piece of state and recall it later — possibly from a different agent.

## Short-term vs long-term

- **Short-term (working) memory** — scoped to a session (`context_id`). Holds the current task's context: intermediate results, pending state. Think "scratchpad for this session".
- **Long-term memory** — persistent and searched by semantic similarity. Holds facts, past results, preferences that should outlive a single session.

## Requirements

The built-in memory API talks to the Agent Memory Server. Agents receive two environment variables (the swarm scaffolding sets these automatically):

| Variable | Purpose |
|----------|---------|
| `AGENT_MEMORY_URL` | AMS base URL, e.g. `http://my-project-agent-memory:8000` |
| `CONTEXT_ID` | Default session id used when you don't pass one explicitly |

If `AGENT_MEMORY_URL` is not set, every memory call **degrades gracefully** — writes return `False`, reads return `""`. Memory never blocks your agent.

See [Environment Variables](../reference/environment-variables.md#agent-memory-redis-ams) for the full AMS configuration.

## Writing memory

Import the write functions from `abi_core.agent` and call them inside a step or task:

```python
from abi_core.agent import add_short_term_memory, add_long_term_memory

@agent.step(name="process", input_map={"data": "$input.data", "context_id": "$input.context_id"})
async def process(data, context_id):
    result = do_work(data)

    # Short-term: remember within this session
    await add_short_term_memory(
        topic="processing",
        task="data_pipeline",
        content=f"Processed {len(data)} records, result={result}",
        context_id=context_id,
    )

    # Long-term: persist a fact for future sessions
    await add_long_term_memory(
        topic="user_preference",
        task="report_format",
        content="User prefers CSV exports over PDF",
        context_id=context_id,
    )
    return {"result": result}
```

### Parameters

Both write functions share the same signature:

```python
await add_short_term_memory(topic, task, content, context_id=None, memory_url=None) -> bool
await add_long_term_memory(topic, task, content, context_id=None, memory_url=None) -> bool
```

| Parameter | Description |
|-----------|-------------|
| `topic` | A label for the memory (e.g. `"user_preference"`). Stored as a searchable topic. |
| `task` | The task/entity this memory is about (e.g. `"report_format"`). Stored as an entity. |
| `content` | The memory text. |
| `context_id` | Session id. Optional — falls back to the `CONTEXT_ID` env var. |
| `memory_url` | AMS URL. Optional — falls back to the `AGENT_MEMORY_URL` env var. |

Both return `True` on success, `False` if memory is unavailable.

## Reading memory

```python
from abi_core.agent import (
    get_short_term_memory,
    get_long_term_memory,
    recall_memory_context,
)

# Get this session's working memory as text
recent = await get_short_term_memory(context_id=context_id)

# Semantic search over long-term memory
matches = await get_long_term_memory("report format preferences", limit=5)

# Hydrate a query with relevant memory (ready to inject into a system prompt)
context = await recall_memory_context("generate the quarterly report", context_id=context_id)
```

`recall_memory_context` is the most convenient for LLM calls — it combines session and long-term memory into a single block of context text you can prepend to your system prompt:

```python
from abi_core.agent import invoke, recall_memory_context

memory = await recall_memory_context(query, context_id=context_id)
system_prompt = base_prompt
if memory:
    system_prompt = f"{base_prompt}\n\n## Relevant context:\n{memory}"

result = await invoke(config.LLM_CONFIG, query, system_prompt=system_prompt)
```

## Letting the LLM recall memory (tools)

To let the LLM decide when to look something up, add the ready-made memory tools to your agent:

```python
from abi_core.memory import MEMORY_TOOLS  # [get_long_term_memory, get_short_term_memory]

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            llm_config=config.LLM_CONFIG,
            tools=[*MEMORY_TOOLS],  # add your own tools too
            system_prompt="...",
        )
```

The LLM can then call `get_long_term_memory(query)` or `get_short_term_memory()` on its own when it needs prior context. These tools resolve `context_id` and the AMS URL from the environment, so the model only supplies a query (or nothing).

## Graceful degradation

Every memory operation is best-effort:

- If the AMS is unreachable or `agent-memory-client` isn't installed, writes return `False` and reads return `""`.
- No exception is raised, so a memory outage never breaks a request.

This is intentional: memory is an enhancement, not a hard dependency. Your agent keeps working even when memory is down — it just loses continuity until the AMS recovers.

## Next step

👉 [Testing Agents](05-testing-agents.md)
