# MCP Transport Upgrade Guide

## Overview

ABI-Core now supports **two transport protocols** for MCP communication:

1. **SSE (Server-Sent Events)** - Default, simple unidirectional streaming
2. **Streamable HTTP** - New, bidirectional streaming with better performance

## What Changed

### Before (v1.5.10 and earlier)

```python
# Only SSE supported
async with client.init_session(
    host="localhost",
    port=10100,
    transport="sse"
) as session:
    pass
```

### After (v1.5.11+)

```python
# Both SSE and Streamable HTTP supported
async with client.init_session(
    host="localhost",
    port=10100,
    transport="streamable-http"  # New option!
) as session:
    pass
```

## Quick Start

### Using SSE (Default)

```python
from abi_core.abi_mcp import client

async with client.init_session(
    host="localhost",
    port=10100,
    transport="sse"  # Default
) as session:
    result = await client.find_agent(
        session,
        "Find trading agent",
        ctx={"agent_id": "agent://client"}
    )
```

### Using Streamable HTTP

```python
from abi_core.abi_mcp import client

async with client.init_session(
    host="localhost",
    port=10100,
    transport="streamable-http"  # New!
) as session:
    result = await client.find_agent(
        session,
        "Find trading agent",
        ctx={"agent_id": "agent://client"}
    )
```

### Using Environment Variables

```bash
# Set transport via environment
export MCP_TRANSPORT=streamable-http
export MCP_HOST=localhost
export MCP_PORT=10100
```

```python
from abi_core.common.utils import get_mcp_server_config
from abi_core.abi_mcp import client

# Automatically uses environment configuration
config = get_mcp_server_config()

async with client.init_session(
    config.host,
    config.port,
    config.transport
) as session:
    # Use session
    pass
```

## Transport Comparison

| Feature | SSE | Streamable HTTP |
|---------|-----|-----------------|
| **Direction** | Unidirectional | Bidirectional |
| **Performance** | Good | Better |
| **Latency** | ~10-50ms | ~5-20ms |
| **Endpoint** | `/sse` | `/mcp` |
| **Use Case** | Simple queries | Complex workflows |
| **Default** | ✅ Yes | No |

## Migration Checklist

- [ ] **No action required** - SSE remains the default
- [ ] **Optional**: Test Streamable HTTP in development
- [ ] **Optional**: Update environment variables to use Streamable HTTP
- [ ] **Optional**: Update Docker Compose files with `MCP_TRANSPORT` variable

## Docker Compose Example

```yaml
services:
  orchestrator:
    environment:
      - MCP_HOST=semantic-layer
      - MCP_PORT=10100
      - MCP_TRANSPORT=streamable-http  # Optional: use new transport
    depends_on:
      - semantic-layer

  semantic-layer:
    ports:
      - "10100:10100"
    # Must support both /sse and /mcp endpoints
```

## Backward Compatibility

✅ **Fully backward compatible**
- Existing code continues to work without changes
- SSE remains the default transport
- No breaking changes to API

## When to Use Each Transport

### Use SSE When:
- ✅ Simple agent discovery
- ✅ Read-only operations
- ✅ Browser-based clients
- ✅ Default choice for most use cases

### Use Streamable HTTP When:
- ✅ Complex multi-step workflows
- ✅ High-performance requirements
- ✅ Bidirectional communication needed
- ✅ Advanced agent coordination

## Testing

Run the example to test both transports:

```bash
cd abi_core_framework
python examples/mcp_transport_examples.py
```

Run unit tests:

```bash
pytest tests/test_mcp_transports.py -v
```

## Documentation

- **Full Guide**: [docs/user-guide/mcp-transports.md](user-guide/mcp-transports.md)
- **Examples**: [examples/mcp_transport_examples.py](../examples/mcp_transport_examples.py)
- **Tests**: [tests/test_mcp_transports.py](../tests/test_mcp_transports.py)

## Troubleshooting

### Transport Not Supported Error

```python
# Error: Unsupported transport type: xyz
# Solution: Use 'sse' or 'streamable-http'

async with client.init_session(
    host="localhost",
    port=10100,
    transport="sse"  # Valid: 'sse' or 'streamable-http'
) as session:
    pass
```

### Connection Issues

```bash
# Check if semantic layer is running
curl http://localhost:10100/health

# Check SSE endpoint
curl http://localhost:10100/sse

# Check Streamable HTTP endpoint
curl http://localhost:10100/mcp
```

## Support

For questions or issues:
- **GitHub Issues**: [abi-core/issues](https://github.com/Joselo-zn/abi-core/issues)
- **Documentation**: [abi-core.readthedocs.io](https://abi-core.readthedocs.io)
- **Email**: jl.mrtz@gmail.com

---

**Version**: 1.5.11+  
**Date**: January 2025  
**Status**: ✅ Production Ready
