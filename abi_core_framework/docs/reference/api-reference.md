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
| `@agent.sandboxed` | Lets a step or task run code in the governed sandbox; the function must take a `run_id` argument. See [Code Execution Sandbox](../production/08-sandbox.md). |
| `@agent.task_async(name, max_retries, base_delay, on_success, on_error)` | Fire-and-forget background function — alpha. See [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md). |
| `@agent.task_schedule(name, trigger, trigger_args, overlap_policy, fail_mode, ...)` | Recurring job on APScheduler, gated by overlap check + OPA — alpha. See [Background & Scheduled Tasks](../production/06-background-and-scheduled-tasks.md). |

### Methods

| Method | Description |
|--------|-------------|
| `agent.execute_step(name, **kwargs)` | Run a step by name. Honours the step's declared `timeout`, as the DAG does |
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
yield AgentResponse.error("Took too long", code="timeout", max_wait=180)  # code → meta.error_code
yield AgentResponse.text("Plain text response")
yield AgentResponse.input_required("Need more info: ...")
yield AgentResponse.element("image", {"url": url}, name="Chart")   # rich element
yield AgentResponse.status("Planning...", phase=RunPhase.PLANNING.value)  # timeline phase
```

`error(message, code=None, **meta)` puts `code` (and any extra keys) in `meta.error_code`, so a client can show its own localized text; `message` stays the English fallback. `AgentResponse.error_from(exc)` builds one from an exception, keeping its `error_code` and `max_wait` when it has them — the bundled Chainlit UI shows timeouts in the browser's language this way. `element()` is covered in [Rich Elements](../single-agent/10-rich-elements.md); `phase` and the other progress keys in [Run Progress](../single-agent/11-run-progress.md) (`from abi_core.agent.agent_response import RunPhase`).

---

## invoke() — LLM calls

```python
from abi_core.agent.llm_provider import invoke

result = await invoke(config.LLM_CONFIG, "Your prompt here")
result = await invoke(config.LLM_CONFIG, prompt, tools=[my_tool])        # With tools
result = await invoke(config.LLM_CONFIG, prompt, system_prompt="...")    # Custom system
result = await invoke(config.LLM_CONFIG, prompt, tools=[my_tool],
                      recursion_limit=30)                                # More tool calls
result = await invoke(config.LLM_CONFIG, prompt, tools=[my_tool],
                      thread_id="gen-1", checkpointer=saver)             # Keep the conversation
```

- `required_tools` — tool names the model **must** call: `invoke(config.LLM_CONFIG, prompt, tools=[write_file], required_tools=["write_file"])`. If the model answers without calling one, it gets one more try with a reminder. If it still skips it, ABI calls the tool itself with arguments taken from the model's answer — this works for tools whose parameters are `filename`, `content` and/or `command`.
- `recursion_limit` — maximum LangGraph steps of the tool-calling agent (default 10; each tool call costs two steps). Size it to the work: a task that reads and writes several files needs more.
- `checkpointer` — a LangGraph checkpointer that keeps the tool-calling conversation after the call returns. A later `invoke` with the same `thread_id` and checkpointer continues it Without a `checkpointer`, `thread_id` alone does not carry anything between calls — each `invoke` starts fresh. For conversation memory across requests, see [Agents with Memory](../single-agent/04-agents-with-memory.md).

---

## invoke_classifier() — decision-model calls

```python
from abi_core.agent import invoke_classifier, ClassifierError

answers = await invoke_classifier(
    state="Customer message: Where is my order?",
    questions={"intent": {"type": "choice", "instructions": "What does the customer want?",
                          "criteria": {"order": "About one of their orders.", "faq": "A general question."}}},
    model=None, base_url=None, timeout=60.0,     # defaults: CLASSIFIER_MODEL, CLASSIFIER_BASE_URL
)
answers["intent"]["choice"], answers["intent"]["confidence"], answers["intent"]["probabilities"]
```

- Calls a decision model (default `laya`) on Ollama's `/v1/systemone`; needs Ollama 0.40 or later. Not a chat model: it scores options and returns probabilities, it doesn't generate text.
- Question types and their `criteria`: `choice` — a dict of 2–26 options → `choice`, `probabilities`, `confidence`; `noul` — `{"true": ..., "false": ...}` → `noul`, the probability of true; `score` — a **list** of 2–10 levels, lowest first → `score` (the expected level, from 0), `legend`, `probabilities`, `confidence`. Up to 64 questions per call.
- Raises `ValueError` for a malformed request (before any call) and `ClassifierError` when the model is unreachable, rejects the request or answers incompletely.
- See [Fast Classification](../single-agent/12-fast-classification.md).

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

---

## Which task runs, and what it receives

When a request reaches an agent that has `@agent.task` functions, the agent picks one:

1. The task whose `task_id` matches the request's `task_id`
2. Otherwise a task named `route_to_task`, or `main`
3. Otherwise the first task registered

The task is called with only the arguments its signature declares, out of `query` (the request text, unchanged), `context_id` (the session) and `task_id`. A task written as `async def chat(query)` keeps working; one written as `async def chat(query, context_id=None)` receives the session id. `agent.execute_step(...)` does the same for steps: `context_id` and `task_id` are dropped if the step doesn't declare them, while any other unexpected argument still raises a `TypeError`.

---

## Web interface endpoints

An agent created with `--with-web-interface` serves, on `WEB_INTERFACE_PORT`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/stream` | POST | `{"query": "..."}` → Server-Sent Events, one per `AgentResponse` |
| `/query` | POST | Same body, one final answer |
| `/session/start`, `/session/rotate`, `/session/end` | POST | Session tokens — see [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md) |
| `/health` | GET | Liveness |
| `/api/tags`, `/api/version`, `/api/ps`, `/api/chat`, `/api/generate` | GET/POST | Ollama-compatible endpoints, so [Open WebUI](https://docs.openwebui.com/) can use the agent as if it were a model |

To keep one conversation per Open WebUI user and chat, set `OPENWEBUI_JWT_SECRET` on the agent to the same value as Open WebUI's `FORWARD_USER_INFO_HEADER_JWT_SECRET`, and set `ENABLE_FORWARD_USER_INFO_HEADERS=true` in Open WebUI. The agent then verifies the user identity Open WebUI signs; an identity that doesn't verify gets a 401. Without it, the agent falls back to its own session token. `ABI_SESSION_REQUIRED=true` makes those routes reject requests that carry neither — see [Environment Variables](environment-variables.md#session-management).

---

## Client (`abi_core.client`)

```python
from abi_core.client import AgentStreamClient

client = AgentStreamClient("http://localhost:8002")   # one instance per conversation
async for event in client.stream("Hello"):
    print(event.get("response_type"), event.get("content"))
```

Starts a session on first use, sends its token with every message, decodes each event into a dict, and drops a token the server no longer recognizes. Failures come back as a `{"response_type": "error", ...}` event, not an exception. See [Testing Agents](../single-agent/05-testing-agents.md#talk-to-it-from-python).

---

## Helpers

```python
from abi_core.common.retry import retry_with_backoff
from abi_core.common.model_tools import list_available_models, find_model, pull_model
from abi_core.common.qr_code import generate_qr_png
from abi_core.common.library_tools import write_pdf
```

| Helper | What it does |
|--------|--------------|
| `await retry_with_backoff(fn, *args, max_retries=3, base_delay=1.0, max_delay=None, retryable=None, on_retry=None, **kwargs)` | Calls `fn` (sync or async), retrying failures with exponential backoff. `retryable(exc)` can opt an exception out; `on_retry(attempt, exc)` runs before each wait |
| `await list_available_models(hosts=None)` | `{model_name: host_url}` across one or more Ollama hosts |
| `await find_model(model, hosts=None)` | The host that has `model`, or `None` |
| `await pull_model(model, host=None)` | Download `model` into Ollama |
| `generate_qr_png(data)` | PNG bytes of a QR code for `data` (needs the `ui` extra). In a response, prefer `AgentResponse.element("qr", {"data": ...})` |
| `write_pdf` | A LangChain tool that renders text as a PDF in the agent's workspace (`WORKSPACE`, default `/app/workspace`). Call it with `write_pdf.invoke({"filename": "report.pdf", "content": "..."})`, or hand it to a model via `invoke(..., tools=[write_pdf])` |
