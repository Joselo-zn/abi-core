# MCPToolkit

`MCPToolkit` is the Python interface for calling any MCP tool on the Semantic Layer. One line per tool call, no boilerplate.

## Basic usage

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Call any tool as a method
result = await toolkit.find_agent(query="analyze data")          # built-in
result = await toolkit.search_tool_registry(query="parse a PDF")  # built-in
result = await toolkit.store_document(content="...")              # one you added

```

That's it. The toolkit handles MCP sessions, HMAC auth, response parsing, and error handling.

The main tools the Semantic Layer ships with are `find_agent`, `recommend_agents`, `check_agent_capability`, `register_agent`, `unregister_agent`, `register_tool`, `get_tool`, `update_tool`, `delete_tool`, `search_tool_registry` and `echo_tool`. Any other name on this page (`store_document`, `calculate_metrics`, `bigquery_search`, `my_custom_tool`) stands for a tool you add yourself — see [Extending the Semantic Layer](04-extending-semantic-layer.md).

## How it works

When you call `toolkit.some_tool(...)`:

1. Opens an MCP session to the Semantic Layer
2. Builds auth context from your agent card (HMAC)
3. Calls the tool with your parameters
4. Returns the tool's value: its structured result when the server sends one (a list comes back whole, an empty list as `[]`), otherwise the JSON in the response
5. On failure, returns `{"error": "..."}`

## Explicit call

If the tool name is dynamic:

```python
tool_name = "calculate_metrics"
result = await toolkit.call(tool_name, start_date="2024-01-01")
```

## Call with retry

For tools that might fail due to network issues:

```python
result = await toolkit.call_with_retry(
    "bigquery_search",
    max_retries=3,
    retry_delay=2.0,
    query="SELECT * FROM sales"
)
```

Retries automatically on session/connection errors with exponential backoff.

## List available tools

```python
# Just names
tools = await toolkit.list_tools()
# ["find_agent", "register_agent", "store_document", ...]

# With descriptions and input schemas
tools = await toolkit.list_tools_detailed()
# [{"name": "find_agent", "description": "...", "inputSchema": {...}}, ...]
```

## Search tools by capability

```python
matches = await toolkit.search_tools("store data for later retrieval")
# Returns tools whose name/description matches your query
```

## Check if a tool exists

```python
if await toolkit.has_tool("my_custom_tool"):
    result = await toolkit.my_custom_tool(param="value")
```

## Error handling

MCPToolkit never throws on tool errors — it returns a dict with an `"error"` key:

```python
result = await toolkit.some_tool(param="value")

if "error" in result:
    print(f"Failed: {result['error']}")
else:
    print(f"Success: {result}")
```

## Using in steps

```python
import json

from app import agent
from abi_core.common.semantic_tools import MCPToolkit


@agent.step(name="save_result")
async def save_result(data, topic):
    """Store results in the Semantic Layer."""
    toolkit = MCPToolkit()
    await toolkit.store_document(
        content=json.dumps(data),
        metadata={"type": "result", "topic": topic}
    )
    return {"stored": True}
```

## Global instance

A pre-configured global instance is available:

```python
from abi_core.common.semantic_tools import mcp_toolkit

result = await mcp_toolkit.my_tool(param="value")
```

## Next step

👉 [Planner & Orchestrator](../orchestration/01-planner-orchestrator.md)
