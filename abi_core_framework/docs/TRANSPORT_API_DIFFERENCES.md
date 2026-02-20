# MCP Transport API - Key Difference

## Overview

**Important:** SSE and Streamable HTTP transports have a **subtle but important difference** in their return values.

## The Key Difference

### SSE Transport - Returns 2 Elements

```python
from mcp.client.sse import sse_client
from mcp import ClientSession

# SSE returns (read_stream, write_stream)
async with sse_client(url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        # Use session
```

### Streamable HTTP Transport - Returns 3 Elements

```python
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

# Streamable HTTP returns (read_stream, write_stream, connection_metadata)
async with streamable_http_client(url) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        # Use session
```

**The third element contains connection metadata and is typically ignored using `_`.**

## Official Example

From the [MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk):

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    # Connect to a streamable HTTP server
    # Note the 3 elements: read_stream, write_stream, and metadata (_)
    async with streamable_http_client("http://localhost:8000/mcp") as (
        read_stream,
        write_stream,
        _,  # Connection metadata (ignored)
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")

asyncio.run(main())
```

## ABI-Core Implementation

The `abi_core.abi_mcp.client.init_session()` function handles both transports with the same logic:

```python
@asynccontextmanager
async def init_session(host, port, transport='sse'):
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        
        # SSE: unpack streams and create session
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                await session.initialize()
                yield session
    
    elif transport == 'streamable-http':
        url = f'http://{host}:{port}/mcp'
        
        # Streamable HTTP: Same API as SSE!
        async with streamable_http_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                await session.initialize()
                yield session
```

## Return Type Comparison

| Transport | Return Type | Elements | Unpacking | Session Creation |
|-----------|-------------|----------|-----------|------------------|
| **SSE** | `(ReadStream, WriteStream)` | 2 | `(read, write)` | Manual via `ClientSession()` |
| **Streamable HTTP** | `(ReadStream, WriteStream, Metadata)` | 3 | `(read, write, _)` | Manual via `ClientSession()` |

**Key Difference:** Streamable HTTP returns an additional third element (connection metadata) that is typically ignored.

## Code Examples

### Example 1: Direct Usage - Both Use Same Pattern

```python
# SSE
async with sse_client('http://localhost:10100/sse') as (read, write):
    async with ClientSession(read_stream=read, write_stream=write) as session:
        await session.initialize()
        result = await session.call_tool('find_agent', {'query': 'test'})

# Streamable HTTP - Same pattern!
async with streamable_http_client('http://localhost:10100/mcp') as (read, write):
    async with ClientSession(read_stream=read, write_stream=write) as session:
        await session.initialize()
        result = await session.call_tool('find_agent', {'query': 'test'})
```

### Example 2: Using ABI-Core Wrapper

```python
from abi_core.abi_mcp import client

# Both transports use the same API
async with client.init_session('localhost', 10100, 'sse') as session:
    result = await client.find_agent(session, 'test', ctx={})

async with client.init_session('localhost', 10100, 'streamable-http') as session:
    result = await client.find_agent(session, 'test', ctx={})
```

## Testing Considerations

### Mocking Both Transports - Same Pattern

```python
@patch('abi_core.abi_mcp.client.sse_client')
async def test_sse(mock_sse):
    mock_read = AsyncMock()
    mock_write = AsyncMock()
    mock_session = AsyncMock()
    
    # SSE returns tuple
    mock_sse.return_value.__aenter__.return_value = (mock_read, mock_write)
    
    with patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
        mock_client_session.return_value.__aenter__.return_value = mock_session
        # Test code

@patch('abi_core.abi_mcp.client.streamable_http_client')
async def test_http(mock_http):
    mock_read = AsyncMock()
    mock_write = AsyncMock()
    mock_session = AsyncMock()
    
    # Streamable HTTP also returns tuple - same as SSE!
    mock_http.return_value.__aenter__.return_value = (mock_read, mock_write)
    
    with patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
        mock_client_session.return_value.__aenter__.return_value = mock_session
        # Test code
```

## Troubleshooting

### Error: "too many values to unpack (expected 2)"

**Cause:** This error should NOT occur with the official MCP SDK as both transports return tuples.

**If you see this error:**
1. Check your MCP SDK version: `pip show mcp`
2. Update to latest: `pip install --upgrade mcp`
3. Verify you're using the correct import:
   ```python
   from mcp.client.streamable_http import streamable_http_client
   ```

### Correct Usage for Both Transports

```python
# ✅ Correct for both SSE and Streamable HTTP
async with sse_client(url) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

async with streamable_http_client(url) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
```

## Design Rationale

### Why Same API?

Both transports use the same API for consistency:

1. **Unified Interface:**
   - Easier to switch between transports
   - Same code patterns
   - Consistent error handling

2. **Stream-Based Architecture:**
   - Both use bidirectional streams
   - Same session management
   - Compatible abstractions

### Benefits of Unified API

- ✅ Easy transport switching
- ✅ Consistent code patterns
- ✅ Simplified testing
- ✅ Better developer experience
- ✅ No special cases needed

## Best Practices

### 1. Use ABI-Core Wrapper

```python
# ✅ Recommended - Use wrapper
from abi_core.abi_mcp import client

async with client.init_session(host, port, transport) as session:
    # Works for both SSE and Streamable HTTP
    pass
```

### 2. Document Transport Choice

```python
def connect_to_mcp(transport='sse'):
    """Connect to MCP server.
    
    Args:
        transport: 'sse' (default) or 'streamable-http'
        
    Note:
        SSE: Unidirectional streaming, simpler
        Streamable HTTP: Bidirectional, better performance
    """
    pass
```

### 3. Handle Both in Tests

```python
@pytest.mark.parametrize('transport', ['sse', 'streamable-http'])
async def test_both_transports(transport):
    async with client.init_session('localhost', 10100, transport) as session:
        # Test works for both transports
        pass
```

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [SSE Standard](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [ABI-Core Transport Guide](user-guide/mcp-transports.md)

---

**Last Updated:** January 2025  
**ABI-Core Version:** 1.5.11+
