# MCPToolkit

`MCPToolkit` is the Python interface for calling any MCP tool on the Semantic Layer. One line per tool call, no boilerplate.

## Basic usage

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Call any tool as a method
result = await toolkit.find_agent(query="analyze data")
result = await toolkit.store_document(content="...", metadata={...})
result = await toolkit.my_custom_tool(param1="value", param2=123)
```

That's it. The toolkit handles MCP sessions, HMAC auth, response parsing, and error handling.

## How it works

When you call `toolkit.some_tool(...)`:

1. Opens an MCP session to the Semantic Layer
2. Builds auth context from your agent card (HMAC)
3. Calls the tool with your parameters
4. Parses the JSON response
5. Returns a dict (or `{"error": "..."}` on failure)

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
