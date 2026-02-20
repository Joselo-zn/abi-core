# MCP Transport Protocols

ABI-Core supports two transport protocols for MCP (Model Context Protocol) communication:

1. **SSE (Server-Sent Events)** - Default, unidirectional streaming
2. **Streamable HTTP** - Bidirectional streaming with better performance

## Transport Implementation Details

### SSE Transport - 2 Elements

SSE returns a tuple with 2 elements:

```python
from mcp.client.sse import sse_client
from mcp import ClientSession

# SSE returns (read_stream, write_stream)
async with sse_client(url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        # Use session
```

### Streamable HTTP Transport - 3 Elements

Streamable HTTP returns a tuple with 3 elements:

```python
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

# Streamable HTTP returns (read_stream, write_stream, connection_metadata)
# The third element contains connection metadata and is typically ignored
async with streamable_http_client(url) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        # Use session
```

**Key Difference:** SSE returns 2 elements, Streamable HTTP returns 3 elements (the third is connection metadata).

| Feature | SSE | Streamable HTTP |
|---------|-----|-----------------|
| **Direction** | Unidirectional (server → client) | Bidirectional |
| **Performance** | Good | Better |
| **Browser Support** | Excellent | Modern browsers |
| **Firewall Friendly** | Yes | Yes |
| **Connection Type** | Long-lived | Request/Response |
| **Use Case** | Simple streaming | Complex interactions |

## Configuration

### Environment Variables

Configure the transport via environment variables:

```bash
# Transport type: 'sse' or 'streamable-http'
export MCP_TRANSPORT=sse

# MCP server connection
export MCP_HOST=localhost
export MCP_PORT=10100
```

### Programmatic Configuration

```python
from abi_core.common.types import ServerConfig

# SSE Transport (default)
config = ServerConfig(
    host="localhost",
    port=10100,
    transport="sse",
    url="http://localhost:10100"
)

# Streamable HTTP Transport
config = ServerConfig(
    host="localhost",
    port=10100,
    transport="streamable-http",
    url="http://localhost:10100"
)
```

## Usage Examples

### SSE Transport

```python
import asyncio
from abi_core.abi_mcp import client

async def use_sse():
    async with client.init_session(
        host="localhost",
        port=10100,
        transport="sse"
    ) as session:
        # Find agent
        result = await client.find_agent(
            session,
            "Find trading agent",
            ctx={"agent_id": "agent://client"}
        )
        print(result.content[0].text)

asyncio.run(use_sse())
```

### Streamable HTTP Transport

```python
import asyncio
from abi_core.abi_mcp import client

async def use_streamable_http():
    async with client.init_session(
        host="localhost",
        port=10100,
        transport="streamable-http"
    ) as session:
        # Find agent
        result = await client.find_agent(
            session,
            "Find trading agent",
            ctx={"agent_id": "agent://client"}
        )
        print(result.content[0].text)

asyncio.run(use_streamable_http())
```

### Dynamic Transport Selection

```python
import os
import asyncio
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def use_dynamic_transport():
    # Get config from environment
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Use session
        tools = await session.list_tools()
        print(f"Available tools: {[t.name for t in tools.tools]}")

asyncio.run(use_dynamic_transport())
```

## Server Endpoints

The MCP client automatically selects the correct endpoint based on transport:

| Transport | Endpoint | URL Example |
|-----------|----------|-------------|
| SSE | `/sse` | `http://localhost:10100/sse` |
| Streamable HTTP | `/mcp` | `http://localhost:10100/mcp` |

## Agent Configuration

### Orchestrator Agent

```python
# config/config.py
import os

class Config:
    # MCP Configuration
    MCP_HOST: str = os.getenv('MCP_HOST', 'localhost')
    MCP_PORT: int = int(os.getenv('MCP_PORT', '10100'))
    MCP_TRANSPORT: str = os.getenv('MCP_TRANSPORT', 'sse')
```

### Planner Agent

```python
# config/config.py
import os

class Config:
    # MCP Configuration
    MCP_HOST: str = os.getenv('MCP_HOST', 'localhost')
    MCP_PORT: int = int(os.getenv('MCP_PORT', '10100'))
    MCP_TRANSPORT: str = os.getenv('MCP_TRANSPORT', 'sse')
```

## Docker Compose Configuration

```yaml
services:
  orchestrator:
    environment:
      - MCP_HOST=semantic-layer
      - MCP_PORT=10100
      - MCP_TRANSPORT=sse  # or streamable-http
    depends_on:
      - semantic-layer

  planner:
    environment:
      - MCP_HOST=semantic-layer
      - MCP_PORT=10100
      - MCP_TRANSPORT=sse  # or streamable-http
    depends_on:
      - semantic-layer

  semantic-layer:
    ports:
      - "10100:10100"
    # Server must support both /sse and /mcp endpoints
```

## Best Practices

### When to Use SSE

- ✅ Simple agent discovery
- ✅ Read-only operations
- ✅ Browser-based clients
- ✅ Firewall-restricted environments
- ✅ Default choice for most use cases

### When to Use Streamable HTTP

- ✅ Complex multi-step workflows
- ✅ Bidirectional communication needed
- ✅ High-performance requirements
- ✅ Modern infrastructure
- ✅ Advanced agent coordination

## Error Handling

```python
import asyncio
from abi_core.abi_mcp import client

async def robust_connection():
    transports = ['sse', 'streamable-http']
    
    for transport in transports:
        try:
            async with client.init_session(
                host="localhost",
                port=10100,
                transport=transport
            ) as session:
                result = await client.find_agent(
                    session,
                    "Find agent",
                    ctx={"agent_id": "agent://client"}
                )
                print(f"✓ Success with {transport}")
                return result
        except Exception as e:
            print(f"✗ Failed with {transport}: {e}")
            continue
    
    raise Exception("All transports failed")

asyncio.run(robust_connection())
```

## Troubleshooting

### Connection Refused

```bash
# Check if semantic layer is running
curl http://localhost:10100/health

# Check SSE endpoint
curl http://localhost:10100/sse

# Check Streamable HTTP endpoint
curl http://localhost:10100/mcp
```

### Transport Not Supported

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

### Environment Variable Not Set

```bash
# Check current configuration
python -c "from abi_core.common.utils import get_mcp_server_config; print(get_mcp_server_config())"

# Set environment variables
export MCP_TRANSPORT=sse
export MCP_HOST=localhost
export MCP_PORT=10100
```

## Migration Guide

### From SSE-only to Dual Transport

**Before (v1.5.10 and earlier):**
```python
# Only SSE supported
async with client.init_session(
    host="localhost",
    port=10100,
    transport="sse"
) as session:
    pass
```

**After (v1.5.11+):**
```python
# Both SSE and Streamable HTTP supported
async with client.init_session(
    host="localhost",
    port=10100,
    transport="streamable-http"  # New option!
) as session:
    pass
```

### Updating Existing Projects

1. **Update environment variables** (optional):
   ```bash
   # Add to .env or docker-compose.yaml
   MCP_TRANSPORT=streamable-http
   ```

2. **No code changes required** - SSE remains the default

3. **Test both transports**:
   ```bash
   # Test SSE
   MCP_TRANSPORT=sse python your_agent.py
   
   # Test Streamable HTTP
   MCP_TRANSPORT=streamable-http python your_agent.py
   ```

## Performance Considerations

### SSE Performance

- **Latency**: ~10-50ms per request
- **Throughput**: Good for moderate loads
- **Memory**: Low overhead
- **Connections**: One long-lived connection

### Streamable HTTP Performance

- **Latency**: ~5-20ms per request
- **Throughput**: Better for high loads
- **Memory**: Slightly higher overhead
- **Connections**: Request/response pattern

## Security

Both transports support the same security features:

- ✅ Agent authentication via headers
- ✅ OPA policy validation
- ✅ Audit logging
- ✅ Rate limiting
- ✅ IP restrictions

```python
# Security context is transport-agnostic
ctx = {
    "agent_id": "agent://orchestrator",
    "user_email": "user@example.com",
    "timestamp": "2025-01-21T10:00:00Z"
}

result = await client.find_agent(session, "query", ctx)
```

## Next Steps

- [Agent Communication Protocols](../agent_protocols.md)
- [MCP Toolkit Usage](../../examples/mcp_toolkit_usage.py)
- [Complete Integration Example](../../examples/planner_orchestrator_integration.py)

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [SSE Standard](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [ABI-Core Documentation](https://abi-core.readthedocs.io)
