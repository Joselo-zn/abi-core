# FastMCP API Migration Guide

## Overview

FastMCP has updated its API in recent versions. The main change is that `host` and `port` parameters are no longer accepted in the `FastMCP()` constructor. Instead, they must be passed to the `run()` method.

## What Changed

### Before (Old API)

```python
from fastmcp import FastMCP

# ❌ Old way - no longer works
mcp = FastMCP('my-service', host='0.0.0.0', port=8080)
mcp.run(transport='sse')
```

### After (New API)

```python
from fastmcp import FastMCP

# ✅ New way - correct
mcp = FastMCP('my-service')
mcp.run(transport='sse', host='0.0.0.0', port=8080)
```

## Error Message

If you use the old API, you'll see this error:

```
TypeError: FastMCP() no longer accepts host
Pass host to run_http_async() or set FASTMCP_HOST
```

## Migration Steps

### 1. Update Constructor Call

**Before:**
```python
mcp = FastMCP('agent-cards', host=host, port=port)
```

**After:**
```python
mcp = FastMCP('agent-cards')
```

### 2. Update run() Call

**Before:**
```python
mcp.run(transport=transport)
```

**After:**
```python
mcp.run(transport=transport, host=host, port=port)
```

## Complete Example

### Old Code (Broken)

```python
def serve(host, port, transport):
    """Start MCP server"""
    # ❌ This will fail
    mcp = FastMCP('agent-cards', host=host, port=port)
    
    @mcp.tool(name='my_tool')
    async def my_tool(query: str) -> str:
        return f"Result: {query}"
    
    # ❌ Missing host and port
    mcp.run(transport=transport)
```

### New Code (Working)

```python
def serve(host, port, transport):
    """Start MCP server"""
    # ✅ Constructor without host/port
    mcp = FastMCP('agent-cards')
    
    @mcp.tool(name='my_tool')
    async def my_tool(query: str) -> str:
        return f"Result: {query}"
    
    # ✅ Pass host and port to run()
    mcp.run(transport=transport, host=host, port=port)
```

## ABI-Core Updates

All ABI-Core templates and examples have been updated to use the new API:

### Updated Files

1. **Service Templates:**
   - `packages/abi-services/templates/service_semantic_layer/layer/mcp_server/server.py.j2`

2. **Scaffolding Templates:**
   - `packages/abi-cli/src/abi_cli/scaffolding/service_semantic_layer/layer/mcp_server/server.py.j2`

3. **Test Projects:**
   - `testproject/services/semantic_layer/layer/mcp_server/server.py`

### Changes Made

```python
# Before
def serve(host, port, transport):
    mcp = FastMCP('agent-cards', host=host, port=port)
    # ... tool definitions ...
    mcp.run(transport=transport)

# After
def serve(host, port, transport):
    mcp = FastMCP('agent-cards')
    # ... tool definitions ...
    mcp.run(transport=transport, host=host, port=port)
```

## Environment Variables

Alternatively, you can use environment variables:

```bash
export FASTMCP_HOST=0.0.0.0
export FASTMCP_PORT=8080
```

```python
# FastMCP will read from environment
mcp = FastMCP('agent-cards')
mcp.run(transport='sse')  # Uses FASTMCP_HOST and FASTMCP_PORT
```

## Transport Support

The new API supports multiple transports:

```python
# SSE transport (default)
mcp.run(transport='sse', host='0.0.0.0', port=8080)

# Streamable HTTP transport
mcp.run(transport='streamable-http', host='0.0.0.0', port=8080)

# HTTP transport
mcp.run(transport='http', host='0.0.0.0', port=8080)
```

## Troubleshooting

### Error: "FastMCP() no longer accepts host"

**Solution:** Remove `host` and `port` from `FastMCP()` constructor and pass them to `run()` instead.

```python
# ❌ Wrong
mcp = FastMCP('service', host='0.0.0.0', port=8080)

# ✅ Correct
mcp = FastMCP('service')
mcp.run(host='0.0.0.0', port=8080)
```

### Error: "run() missing required argument: 'host'"

**Solution:** Pass `host` and `port` to `run()` method.

```python
# ❌ Wrong
mcp.run(transport='sse')

# ✅ Correct
mcp.run(transport='sse', host='0.0.0.0', port=8080)
```

### Server Not Binding to Correct Address

**Check:** Ensure you're passing the correct host and port to `run()`.

```python
# Bind to all interfaces
mcp.run(transport='sse', host='0.0.0.0', port=8080)

# Bind to localhost only
mcp.run(transport='sse', host='127.0.0.1', port=8080)

# Bind to specific IP
mcp.run(transport='sse', host='192.168.1.100', port=8080)
```

## Testing Your Migration

### 1. Check Syntax

```bash
python3 -m py_compile your_server.py
```

### 2. Test Server Startup

```bash
python3 your_server.py
```

Expected output:
```
[🔄] Starting Agents Cards MCP Server
[🌐] Server config: host=0.0.0.0, port=10100, transport=sse
[🚀] Starting MCP server on 0.0.0.0:10100 with sse transport
```

### 3. Test Connectivity

```bash
# Test health endpoint
curl http://localhost:10100/health

# Test SSE endpoint
curl http://localhost:10100/sse

# Test Streamable HTTP endpoint
curl http://localhost:10100/mcp
```

## Best Practices

### 1. Always Log Configuration

```python
def serve(host, port, transport):
    abi_logging(f'[🌐] Server config: host={host}, port={port}, transport={transport}')
    mcp = FastMCP('agent-cards')
    # ... setup ...
    abi_logging(f'[🚀] Starting MCP server on {host}:{port} with {transport} transport')
    mcp.run(transport=transport, host=host, port=port)
```

### 2. Validate Parameters

```python
def serve(host, port, transport):
    if not host:
        raise ValueError("Host is required")
    if not port or port <= 0:
        raise ValueError("Valid port is required")
    if transport not in ['sse', 'streamable-http', 'http']:
        raise ValueError(f"Unsupported transport: {transport}")
    
    mcp = FastMCP('agent-cards')
    mcp.run(transport=transport, host=host, port=port)
```

### 3. Use Configuration Objects

```python
from dataclasses import dataclass

@dataclass
class ServerConfig:
    host: str = '0.0.0.0'
    port: int = 10100
    transport: str = 'sse'

def serve(config: ServerConfig):
    mcp = FastMCP('agent-cards')
    mcp.run(
        transport=config.transport,
        host=config.host,
        port=config.port
    )
```

## Version Compatibility

| FastMCP Version | API Style | Status |
|-----------------|-----------|--------|
| < 0.2.0 | Old (host in constructor) | ❌ Deprecated |
| >= 0.2.0 | New (host in run()) | ✅ Current |

## Additional Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [ABI-Core MCP Transport Guide](user-guide/mcp-transports.md)

## Support

If you encounter issues after migration:

1. Check that you're using the latest version of `fastmcp`
2. Verify your code matches the examples in this guide
3. Review the error messages carefully
4. Check the [ABI-Core GitHub Issues](https://github.com/Joselo-zn/abi-core/issues)

---

**Last Updated:** January 2025  
**ABI-Core Version:** 1.5.11+  
**FastMCP Version:** 0.2.0+
