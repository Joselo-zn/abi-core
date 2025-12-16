# Extending the Semantic Layer

Customize and extend the semantic layer for your needs.

## Add Custom Metadata

Edit agent cards to add additional information:

```json
{
  "id": "agent://my-agent",
  "metadata": {
    "domain": "finance",
    "region": "LATAM",
    "language": "en",
    "custom_field": "value"
  }
}
```

## Filter by Metadata

```python
# Search agents from a specific domain
agents = await client.find_agents_by_metadata(
    session,
    {"domain": "finance"}
)
```

## Create Custom MCP Tools

You can create custom tools that work with MCPToolkit:

```python
# In your semantic layer MCP server
from mcp.server import Server

server = Server("my-semantic-layer")

@server.call_tool()
async def my_custom_tool(
    param1: str,
    param2: int,
    _request_context: dict = None
) -> dict:
    """Custom tool accessible via MCPToolkit"""
    return {
        "status": "success",
        "data": f"Processed {param1} with {param2}"
    }
```

Then call it from any agent using MCPToolkit:

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()
result = await toolkit.my_custom_tool(param1="value", param2=123)
```

## Next Steps

- [MCPToolkit - Dynamic Tool Access](05-mcp-toolkit.md) - Learn pythonic tool calling
- [Advanced orchestration](../orchestration/01-planner-orchestrator.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
