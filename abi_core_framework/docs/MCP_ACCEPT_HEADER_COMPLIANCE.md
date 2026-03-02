# MCP Accept Header Compliance

## Overview

This document explains how ABI-Core complies with the MCP specification requirement for Accept headers in client requests.

## MCP Specification Requirement

According to the [MCP specification](https://modelcontextprotocol.io/):

> The client MUST include an Accept header, listing both `application/json` and `text/event-stream` as supported content types.

This ensures proper content negotiation between MCP clients and servers, allowing servers to respond with the appropriate content type based on the transport protocol being used.

## Implementation

### SSE Transport

For SSE (Server-Sent Events) transport, ABI-Core explicitly sets the Accept header:

```python
# abi_core/abi_mcp/client.py
if transport == 'sse':
    url = f'http://{host}:{port}/sse'
    
    # MCP spec requires Accept header with both application/json and text/event-stream
    headers = {
        'Accept': 'application/json, text/event-stream'
    }
    
    async with sse_client(url, headers=headers) as (read_stream, write_stream):
        # ... session initialization
```

**Why explicit headers?** The MCP SDK's `sse_client` function by default only sets `Accept: text/event-stream`. To comply with the MCP spec, we explicitly pass headers that include both content types.

### Streamable HTTP Transport

For Streamable HTTP transport, the Accept header is automatically set by the MCP SDK:

```python
# From mcp.client.streamable_http.StreamableHTTPTransport
class StreamableHTTPTransport:
    def __init__(self, url, headers=None, ...):
        self.request_headers = {
            'accept': 'application/json, text/event-stream',  # Automatically set
            'content-type': 'application/json',
            **self.headers,
        }
```

**No explicit headers needed:** The `StreamableHTTPTransport` class in the MCP SDK automatically includes the correct Accept header, so ABI-Core doesn't need to set it explicitly.

## Verification

You can verify the Accept headers are being sent correctly:

### Using Network Inspection

```python
import asyncio
import logging
from abi_core.abi_mcp import client

# Enable debug logging to see headers
logging.basicConfig(level=logging.DEBUG)

async def verify_headers():
    # Test SSE
    async with client.init_session(
        host="localhost",
        port=10100,
        transport="sse"
    ) as session:
        print("✓ SSE connection established with correct headers")
    
    # Test Streamable HTTP
    async with client.init_session(
        host="localhost",
        port=10100,
        transport="streamable-http"
    ) as session:
        print("✓ Streamable HTTP connection established with correct headers")

asyncio.run(verify_headers())
```

### Using Server-Side Logging

On the MCP server side, you can log incoming request headers:

```python
# In your FastMCP server
from fastapi import Request

@app.middleware("http")
async def log_headers(request: Request, call_next):
    accept_header = request.headers.get("accept", "")
    print(f"Accept header: {accept_header}")
    
    # Verify compliance
    if "application/json" in accept_header and "text/event-stream" in accept_header:
        print("✓ Client is MCP compliant")
    else:
        print("✗ Client is NOT MCP compliant")
    
    response = await call_next(request)
    return response
```

## Testing

Unit tests verify Accept header compliance:

```python
# tests/test_mcp_accept_headers.py
import pytest
from unittest.mock import patch, MagicMock
from abi_core.abi_mcp import client

@pytest.mark.asyncio
async def test_sse_accept_header():
    """Verify SSE transport sends correct Accept header"""
    with patch('abi_core.abi_mcp.client.sse_client') as mock_sse:
        mock_sse.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        
        async with client.init_session("localhost", 10100, "sse"):
            pass
        
        # Verify headers were passed
        call_args = mock_sse.call_args
        headers = call_args.kwargs.get('headers', {})
        
        assert 'Accept' in headers
        assert 'application/json' in headers['Accept']
        assert 'text/event-stream' in headers['Accept']

@pytest.mark.asyncio
async def test_streamable_http_accept_header():
    """Verify Streamable HTTP transport has correct Accept header"""
    # The StreamableHTTPTransport class automatically sets the header
    # This test verifies the SDK behavior
    from mcp.client.streamable_http import StreamableHTTPTransport
    
    transport = StreamableHTTPTransport("http://localhost:10100/mcp")
    
    assert 'accept' in transport.request_headers
    assert 'application/json' in transport.request_headers['accept']
    assert 'text/event-stream' in transport.request_headers['accept']
```

## Troubleshooting

### Server Rejects Requests

If your MCP server is rejecting requests due to missing or incorrect Accept headers:

1. **Check server logs** for Accept header values
2. **Verify ABI-Core version** - Accept header compliance was added in v1.5.11
3. **Update dependencies**:
   ```bash
   pip install --upgrade abi-core-ai
   ```

### Custom Headers

If you need to add additional custom headers:

```python
# For SSE transport, you can extend the headers
# Note: This is not currently supported in the public API
# but can be added if needed

# For Streamable HTTP, custom headers can be passed:
from mcp.client.streamable_http import streamablehttp_client

custom_headers = {
    'X-Custom-Header': 'value',
    'Authorization': 'Bearer token'
}

async with streamablehttp_client(url, headers=custom_headers) as (read, write, _):
    # The SDK will merge custom headers with default Accept header
    pass
```

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [HTTP Accept Header (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept)
- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)

## Version History

- **v1.5.11**: Added explicit Accept header for SSE transport to comply with MCP specification
- **v1.5.10**: Initial dual transport support (SSE and Streamable HTTP)

## Related Documentation

- [MCP Transport Guide](user-guide/mcp-transports.md)
- [Transport API Differences](TRANSPORT_API_DIFFERENCES.md)
- [Session Management](SESSION_MANAGEMENT.md)
