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
| `@agent.step(name, depends_on, input_map)` | Deterministic DAG node |
| `@agent.task(name, task_id)` | Programmatic orchestrator of steps |
| `@agent.tool(name)` | DAG node + LLM-invocable tool |
| `@agent.mcp_tool(name)` | Remote tool via MCP protocol |

### Methods

| Method | Description |
|--------|-------------|
| `agent.execute_step(name, **kwargs)` | Run a step by name |
| `agent.execute_task(name, query=...)` | Run a task (async generator) |
| `agent.run(agent_instance)` | Compile DAG, start A2A server |
| `agent.get_task_metadata()` | List all registered tasks |

---

## AbiAgent (base class)

```python
from abi_core.agent.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="What it does",
            llm_config={"provider": "ollama", "model": "qwen2.5:3b"},
            tools=[],
            system_prompt="You are...",
        )
```

### Methods

| Method | Description |
|--------|-------------|
| `stream(query, context_id, task_id)` | Main execution — async generator of responses |
| `_run_with_heartbeat(coro, ...)` | Run coroutine with SSE heartbeat |
| `process_answer(session_id, query)` | Session context management |
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

## Utilities

```python
from abi_core.common.utils import (
    abi_logging,           # Log with ABI format
    clean_llm_json,        # Parse JSON from LLM output (handles markdown fences)
    get_mcp_server_config, # Get MCP host/port/transport from env
    yield_chunk_data,      # Convert AgentResponse to SSE bytes
)
```
