# MCPToolkit - Dynamic Tool Access

Learn how to use MCPToolkit for pythonic access to custom MCP tools.

## Overview

MCPToolkit provides a dynamic, pythonic interface for calling custom MCP tools without writing repetitive boilerplate code. Instead of manually managing sessions and parsing responses, you can call any MCP tool as if it were a native Python method.

## Why MCPToolkit?

### Without MCPToolkit

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
from abi_core.security.agent_auth import build_semantic_context_from_card
import json

# Lots of boilerplate for each tool call
async def call_my_tool(param1, param2):
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        context = build_semantic_context_from_card(
            agent_card_path,
            tool_name="my_tool",
            query=json.dumps({"param1": param1, "param2": param2})
        )
        
        response = await client.custom_tool(
            session,
            "my_tool",
            context,
            {"param1": param1, "param2": param2}
        )
        
        # Parse response...
        if hasattr(response, 'content') and response.content:
            result = json.loads(response.content[0].text)
            return result
        return {}
```

### With MCPToolkit

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Simple, pythonic call
result = await toolkit.my_tool(param1="value", param2=123)
```

## Basic Usage

### Initialize Toolkit

```python
from abi_core.common.semantic_tools import MCPToolkit

# Use default configuration
toolkit = MCPToolkit()

# Or use custom configuration
from abi_core.common.utils import get_mcp_server_config

custom_config = get_mcp_server_config()
toolkit = MCPToolkit(
    agent_card_path="/custom/path/agent_card.json",
    mcp_config=custom_config
)
```

### Call Tools Dynamically

The most pythonic way - tools are accessed as attributes:

```python
# Call any MCP tool dynamically
result = await toolkit.my_custom_tool(
    param1="value",
    param2=123,
    param3={"nested": "data"}
)

# Another tool
metrics = await toolkit.calculate_metrics(
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Process data
processed = await toolkit.process_data(
    data_id=456,
    operation="transform"
)
```

### Call Tools Explicitly

If you prefer explicit calls or need dynamic tool names:

```python
# Explicit call method
result = await toolkit.call(
    "my_custom_tool",
    param1="value",
    param2=123
)

# Dynamic tool name
tool_name = "calculate_metrics"
result = await toolkit.call(tool_name, metric="revenue")
```

## Tool Discovery

### List Available Tools

```python
# Get all available MCP tools
tools = await toolkit.list_tools()
print(f"Available tools: {tools}")
# Output: ['find_agent', 'register_agent', 'my_custom_tool', ...]
```

### Check Tool Existence

```python
# Check if a tool exists before calling
if await toolkit.has_tool("my_custom_tool"):
    result = await toolkit.my_custom_tool(param="value")
else:
    print("Tool not available")
```

## Error Handling

MCPToolkit always returns a dictionary. Errors are returned in the response:

```python
result = await toolkit.my_tool(param="value")

# Check for errors
if "error" in result:
    print(f"Error: {result['error']}")
else:
    print(f"Success: {result}")
```

### Robust Error Handling

```python
try:
    result = await toolkit.my_tool(param="value")
    
    if "error" in result:
        # Handle tool-level error
        print(f"Tool error: {result['error']}")
    else:
        # Process successful result
        data = result.get('data', [])
        print(f"Processed {len(data)} items")
        
except Exception as e:
    # Handle connection or system errors
    print(f"System error: {e}")
```

## Real-World Examples

### Example 1: Data Processing Pipeline

```python
from abi_core.common.semantic_tools import MCPToolkit

async def process_pipeline():
    toolkit = MCPToolkit()
    
    # Step 1: Fetch data
    print("Fetching data...")
    data = await toolkit.fetch_data(
        source="database",
        query="SELECT * FROM users WHERE active=true"
    )
    
    if "error" in data:
        print(f"Fetch failed: {data['error']}")
        return
    
    # Step 2: Transform data
    print("Transforming data...")
    transformed = await toolkit.transform_data(
        data=data,
        operations=["normalize", "enrich", "validate"]
    )
    
    if "error" in transformed:
        print(f"Transform failed: {transformed['error']}")
        return
    
    # Step 3: Store results
    print("Storing results...")
    stored = await toolkit.store_results(
        data=transformed,
        destination="cache",
        ttl=3600
    )
    
    if "error" not in stored:
        print("Pipeline completed successfully!")
    else:
        print(f"Storage failed: {stored['error']}")
```

### Example 2: Conditional Tool Execution

```python
async def smart_execution():
    toolkit = MCPToolkit()
    
    # Get available tools
    tools = await toolkit.list_tools()
    
    # Execute tools based on availability
    results = {}
    
    if "analyze_sentiment" in tools:
        results['sentiment'] = await toolkit.analyze_sentiment(
            text="This is amazing!"
        )
    
    if "extract_entities" in tools:
        results['entities'] = await toolkit.extract_entities(
            text="Apple Inc. is based in Cupertino, California."
        )
    
    if "summarize_text" in tools:
        results['summary'] = await toolkit.summarize_text(
            text="Long text here...",
            max_length=100
        )
    
    return results
```

### Example 3: Batch Processing

```python
async def batch_process(items):
    toolkit = MCPToolkit()
    results = []
    
    for item in items:
        # Check if tool exists
        if await toolkit.has_tool(item['tool_name']):
            result = await toolkit.call(
                item['tool_name'],
                **item['params']
            )
            results.append({
                'item_id': item['id'],
                'result': result,
                'success': "error" not in result
            })
        else:
            results.append({
                'item_id': item['id'],
                'error': f"Tool {item['tool_name']} not found",
                'success': False
            })
    
    return results
```

### Example 4: Using in Agent Code

```python
from abi_core.common.semantic_tools import MCPToolkit

class MyAgent:
    def __init__(self):
        self.toolkit = MCPToolkit()
    
    async def process_request(self, user_query: str):
        # Use custom MCP tools in your agent
        
        # Analyze the query
        analysis = await self.toolkit.analyze_query(
            query=user_query,
            context="customer_support"
        )
        
        if "error" in analysis:
            return {"error": "Failed to analyze query"}
        
        # Route to appropriate handler
        intent = analysis.get('intent')
        
        if intent == "technical_support":
            return await self.toolkit.handle_technical_support(
                query=user_query,
                priority=analysis.get('priority', 'normal')
            )
        elif intent == "billing":
            return await self.toolkit.handle_billing(
                query=user_query,
                account_id=analysis.get('account_id')
            )
        else:
            return await self.toolkit.handle_general(
                query=user_query
            )
```

## Global Toolkit Instance

For convenience, a global toolkit instance is available:

```python
from abi_core.common.semantic_tools import mcp_toolkit

# Use the global instance directly
result = await mcp_toolkit.my_tool(param="value")
```

## LangChain Integration

MCPToolkit is compatible with LangChain tools:

```python
from abi_core.common.semantic_tools import custom_call

# Use as LangChain tool
result = await custom_call(
    tool_name="my_custom_tool",
    payload={"param1": "value", "param2": 123}
)
```

Note: `custom_call` internally uses MCPToolkit, so you get the same benefits.

## Best Practices

### 1. Reuse Toolkit Instances

```python
# Good - reuse instance
toolkit = MCPToolkit()
result1 = await toolkit.tool1()
result2 = await toolkit.tool2()

# Avoid - creating multiple instances
result1 = await MCPToolkit().tool1()
result2 = await MCPToolkit().tool2()
```

### 2. Check Tool Availability

```python
# Good - check before calling
if await toolkit.has_tool("optional_tool"):
    result = await toolkit.optional_tool()

# Risky - assume tool exists
result = await toolkit.optional_tool()  # May fail
```

### 3. Handle Errors Gracefully

```python
# Good - check for errors
result = await toolkit.my_tool()
if "error" in result:
    # Handle error
    fallback_result = await toolkit.fallback_tool()

# Risky - assume success
data = result['data']  # May fail if error occurred
```

### 4. Use Type Hints

```python
from typing import Dict, Any

async def process_data(toolkit: MCPToolkit) -> Dict[str, Any]:
    result = await toolkit.process(data="value")
    return result
```

## Advanced Usage

### Custom Configuration

```python
from abi_core.common.semantic_tools import MCPToolkit
from abi_core.common.types import ServerConfig

# Create custom config
custom_config = ServerConfig(
    host="custom-semantic-layer",
    port=10100,
    transport="sse"
)

toolkit = MCPToolkit(
    agent_card_path="/custom/agent_card.json",
    mcp_config=custom_config
)
```

### Debugging

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.INFO)

toolkit = MCPToolkit()

# Calls will log detailed information
result = await toolkit.my_tool(param="value")
# Output:
# [🔧] Calling MCP tool 'my_tool' with args: {'param': 'value'}
# [✅] Tool 'my_tool' executed successfully
```

### Toolkit Information

```python
toolkit = MCPToolkit()

# Get toolkit info
print(toolkit)
# Output: MCPToolkit(host=project-semantic-layer, port=10100, tools not loaded)

# Load tools
await toolkit.list_tools()
print(toolkit)
# Output: MCPToolkit(host=project-semantic-layer, port=10100, 15 tools)
```

## Creating Custom MCP Tools

To create tools that work with MCPToolkit, implement them in your semantic layer's MCP server:

```python
# In your semantic layer MCP server
from mcp.server import Server
from mcp.types import Tool

server = Server("my-semantic-layer")

@server.call_tool()
async def my_custom_tool(
    param1: str,
    param2: int,
    _request_context: dict = None
) -> dict:
    """
    Custom tool that can be called via MCPToolkit
    
    Args:
        param1: First parameter
        param2: Second parameter
        _request_context: Authentication context (automatic)
    
    Returns:
        Result dictionary
    """
    # Your tool logic here
    result = {
        "status": "success",
        "data": f"Processed {param1} with {param2}"
    }
    return result
```

Then call it from any agent:

```python
toolkit = MCPToolkit()
result = await toolkit.my_custom_tool(param1="value", param2=123)
```

## Troubleshooting

### Tool Not Found

```python
# Check if tool is registered
tools = await toolkit.list_tools()
if "my_tool" not in tools:
    print("Tool not registered in MCP server")
```

### Connection Errors

```python
# Verify MCP configuration
from abi_core.common.utils import get_mcp_server_config

config = get_mcp_server_config()
print(f"MCP Host: {config.host}")
print(f"MCP Port: {config.port}")
print(f"MCP Transport: {config.transport}")
```

### Authentication Errors

```python
# Verify agent card path
import os
agent_card = os.getenv('AGENT_CARD')
print(f"Agent Card: {agent_card}")

# Check if file exists
from pathlib import Path
if not Path(agent_card).exists():
    print("Agent card file not found!")
```

## Next Steps

- [Extending Semantic Layer](04-extending-semantic-layer.md) - Create custom MCP tools
- [Agent Discovery](02-agent-discovery.md) - Use built-in discovery tools
- [Semantic Search](03-semantic-search.md) - Search capabilities

---

**Complete Example**: See `examples/mcp_toolkit_usage.py` for a full working example with all features demonstrated.
