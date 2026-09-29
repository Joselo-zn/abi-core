# API Reference

## AbiCore (app runner)

```python
from abi_core.agent import AbiCore

agent = AbiCore(
    web_interface_cls=MyWebInterface,  # Optional
    interface_name="My Agent",         # Optional
)
```

### Decorators

| Decorator | Purpose |
|-----------|---------|
| `@agent.step(name, depends_on, input_map, timeout)` | Deterministic DAG node |
| `@agent.task(name, task_id)` | Programmatic orchestrator of steps |
| `@agent.tool(name)` | DAG node + LLM-invocable tool |
| `@agent.mcp_tool(name)` | Remote tool via MCP protocol |
| `@agent.task_async(name, max_retries, base_delay, on_success, on_error)` | Fire-and-forget background function — alpha. See [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md). |
| `@agent.task_schedule(name, trigger, trigger_args, overlap_policy, fail_mode, ...)` | Recurring job on APScheduler, gated by overlap check + OPA — alpha. See [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md). |

### Methods

| Method | Description |
|--------|-------------|
| `agent.execute_step(name, **kwargs)` | Run a step by name |
| `agent.execute_task(name, query=...)` | Run a task (async generator) |
| `agent.run(agent_instance)` | Compile DAG, start A2A server |
| `agent.get_task_metadata()` | List all registered tasks |
| `agent.execute_task_async(name, context_id=None, **kwargs)` | Launch a `@agent.task_async` function in the background; returns an `async_task_id` immediately |
| `agent.get_async_task_status(async_task_id)` | Poll a background/scheduled task's status (`running`/`done`/`failed`) — `None` if unknown |

---

## AbiAgent (base class)

```python
from abi_core.agent.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="What it does",
            llm_config={"provider": "ollama", "model": "qwen3:latest"},
            tools=[],
            system_prompt="You are...",
        )
```

### Methods

| Method | Description |
|--------|-------------|
| `stream(query, context_id, task_id)` | Main execution — async generator of responses |
| `_run_with_heartbeat(coro, ...)` | Async generator — runs a coroutine, yielding live SSE heartbeats then a final `_HeartbeatDone(result)` |
| `process_answer(session_id, query)` | Session context management |
| `get_session_context`/`update_session_context(context_id, ...)` | Read/merge the session's context dict — see [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md) |
| `record_conversation_turn(context_id, query, response_text, window=5)` | Append a turn to a rolling conversation window; oldest turn promotes to long-term memory past `window` — see [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md#conversation-memory) |
| `record_error`/`record_pending_plan`/`clear_pending_plan` | Generic cross-turn bookkeeping, session-backed |
| `check_health(url, name)` | Static — ping an agent's health endpoint |

---

## AgentResponse

```python
from abi_core.agent.agent_response import AgentResponse

yield AgentResponse.status("Working...")
yield AgentResponse.result({"key": "value"})
yield AgentResponse.error("Something failed")
yield AgentResponse.text("Plain text response")
yield AgentResponse.input_required("Need more info: ...")
yield AgentResponse.success("Final answer")
```

---

## invoke() — LLM calls

```python
from abi_core.agent.llm_provider import invoke

result = await invoke(config.LLM_CONFIG, "Your prompt here")
result = await invoke(config.LLM_CONFIG, prompt, thread_id="session-1")  # With memory
result = await invoke(config.LLM_CONFIG, prompt, tools=[my_tool])        # With tools
result = await invoke(config.LLM_CONFIG, prompt, system_prompt="...")    # Custom system
```

---

## Semantic Tools

```python
from abi_core.common.semantic_tools import (
    tool_find_agent,       # Find one agent by description
    tool_list_agents,      # Find multiple agents
    tool_recommend_agents, # Recommend agents with scores
    tool_check_agent_health,
    tool_register_agent,
    tool_search_tools,     # Search tool registry
    MCPToolkit,            # Dynamic MCP tool caller
    mcp_toolkit,           # Global instance
)
```

### MCPToolkit

```python
toolkit = MCPToolkit()

result = await toolkit.any_tool_name(param="value")     # Dynamic call
result = await toolkit.call("tool_name", param="value") # Explicit call
result = await toolkit.call_with_retry("tool", max_retries=3, param="value")
tools = await toolkit.list_tools()                       # List available
tools = await toolkit.list_tools_detailed()              # With schemas
matches = await toolkit.search_tools("description")     # Search by capability
exists = await toolkit.has_tool("name")                  # Check existence
```

---

## A2A Communication

```python
from abi_core.common.abi_a2a import agent_connection

async for chunk in agent_connection(source_card, target_card, payload):
    # Streaming A2A response
    pass
```

---

## Workflow

```python
from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode, Status

flow = AgentInteractionFlow()
node = InteractionFlowNode(
    task="Do something",
    source_agent_card=my_card,
    target_agent_card=target_card,
    node_key="step-1",
)
flow.add_node(node)
flow.set_source_card(my_card)

async for chunk in flow.run_workflow():
    process(chunk)
```

---

## Memory (`abi_core.memory`)

```{note}
**Alpha.** Backed by the Agent Memory Server — see [Environment Variables → Agent Memory](environment-variables.md#agent-memory-redis-ams).
```

```python
from abi_core.memory import (
    add_short_term_memory,   # (topic, task, content, context_id=None, memory_url=None) -> bool
    add_long_term_memory,    # (topic, task, content, context_id=None, memory_url=None) -> bool
    get_short_term_memory,   # (context_id=None, memory_url=None) -> str
    get_long_term_memory,    # (query, context_id=None, memory_url=None, limit=5) -> str
    recall_memory_context,   # (query, context_id=None, memory_url=None, long_term_limit=3) -> str
    MEMORY_TOOLS,             # LangChain tools: get_long_term_memory, get_short_term_memory,
                               # save_short_term_memory, save_long_term_memory
)
# Also importable from abi_core.agent (add_short_term_memory, add_long_term_memory,
# get_short_term_memory, get_long_term_memory, recall_memory_context).
```

All functions degrade gracefully — on any failure (AMS unreachable, library missing) they
log a warning and return `False`/`""` instead of raising. See
[Built-in Memory API](../single-agent/06-builtin-memory.md).

---

## Artifact Store (`abi_core.common.artifact_store`)

```python
from abi_core.common.artifact_store import (
    ArtifactStore,               # upload/download/list_artifacts/delete/get_url/exists
    upload_workspace_artifacts,  # scan a workspace dir, upload new files, skip `exclude`
    download_artifacts,          # download a list of MinIO keys into a local workspace
    generate_download_urls,      # add 'download_url' (pre-signed) to a list of artifact dicts
    format_artifact_links,       # render artifacts as a markdown links block
)
```

See [Artifact Store](../production/05-artifact-store.md) for usage patterns and the
`ARTIFACT_ENDPOINT` vs `ARTIFACT_PUBLIC_ENDPOINT` distinction.

---

## Utilities

```python
from abi_core.common.utils import (
    abi_logging,                 # Log with ABI format
    clean_llm_json,              # Parse JSON from LLM output (handles markdown fences)
    get_mcp_server_config,       # Get MCP host/port/transport from env
    yield_chunk_data,            # Convert AgentResponse to SSE bytes
    format_plan_summary,         # Render a plan dict as a markdown summary
    format_conversation_summary, # Render a recorded conversation window as prompt text
)
```
