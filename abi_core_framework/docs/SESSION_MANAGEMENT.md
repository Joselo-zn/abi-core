# MCP Session Management Best Practices

## Problem: "Session terminated" Error

### Symptoms

```
[❌] Error calling tool: Session terminated
{'error': 'Tool execution error: Session terminated'}
```

**Server logs:**
```
ResourceWarning: Unclosed <MemoryObjectReceiveStream at 0x...>
```

### Root Cause

The "Session terminated" error occurs when:

1. **Improper session lifecycle management** - Sessions closed before response is fully received
2. **Unclosed streams** - `MemoryObjectReceiveStream` not properly cleaned up
3. **Unhandled exceptions** - Errors that terminate the session prematurely
4. **Timeout issues** - Long-running operations exceeding session timeout

## Solution 1: Proper Session Management (Client Side)

### ✅ Correct Implementation

The ABI-Core client already implements proper session management:

```python
from abi_core.abi_mcp import client

# Context manager ensures proper cleanup
async with client.init_session('localhost', 10100, 'streamable-http') as session:
    # Session is properly managed
    result = await client.find_agent(session, 'query', ctx={})
    # Session automatically cleaned up after use
```

### ❌ Incorrect Implementation

```python
# DON'T DO THIS - Session not properly managed
session = await create_session()
result = await session.call_tool('tool_name', {})
# Session never closed - causes "Session terminated" errors
```

### Implementation Details

The `init_session()` function uses nested context managers:

```python
@asynccontextmanager
async def init_session(host, port, transport='sse'):
    session = None
    try:
        # Outer context: Transport connection
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            try:
                # Inner context: MCP session
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session
            finally:
                # Ensure session cleanup
                if session:
                    logger.debug('Cleaning up session')
    finally:
        # Ensure stream cleanup
        logger.debug('Connection cleanup complete')
```

## Solution 2: Server-Side Configuration

### Configure Session Timeouts

For long-running operations (like BigQuery queries), increase timeouts:

```python
# server.py
from fastmcp import FastMCP

mcp = FastMCP(
    'semantic-layer',
    # Increase timeout for long operations
    session_timeout=300,  # 5 minutes
    health_check_timeout=30
)
```

### Proper Tool Implementation

```python
@mcp.tool(name='query_bigquery')
async def query_bigquery(query: str) -> dict:
    """Execute BigQuery with proper error handling"""
    try:
        # Execute query
        result = await execute_query(query)
        
        # IMPORTANT: Return result before session closes
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        logger.error(f'Query error: {e}', exc_info=True)
        # Return error, don't raise (keeps session alive)
        return {
            'success': False,
            'error': str(e)
        }
```

## Solution 3: Retry Logic

For transient "Session terminated" errors, implement retry logic:

```python
import asyncio
from typing import Optional

async def call_tool_with_retry(
    host: str,
    port: int,
    tool_name: str,
    arguments: dict,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Optional[dict]:
    """Call MCP tool with automatic retry on session errors"""
    
    for attempt in range(max_retries):
        try:
            async with client.init_session(host, port, 'streamable-http') as session:
                result = await session.call_tool(tool_name, arguments)
                return result
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Retry on session errors
            if 'session terminated' in error_msg or 'connection' in error_msg:
                if attempt < max_retries - 1:
                    logger.warning(f'Session error (attempt {attempt + 1}/{max_retries}): {e}')
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
            
            # Don't retry other errors
            raise
    
    raise Exception(f'Failed after {max_retries} attempts')
```

## Solution 4: Connection Pooling

For high-frequency operations, use connection pooling:

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

class MCPConnectionPool:
    """Connection pool for MCP sessions"""
    
    def __init__(self, host: str, port: int, transport: str = 'streamable-http'):
        self.host = host
        self.port = port
        self.transport = transport
        self._session = None
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[ClientSession, None]:
        """Get or create a session"""
        async with self._lock:
            if self._session is None:
                async with client.init_session(
                    self.host,
                    self.port,
                    self.transport
                ) as session:
                    self._session = session
                    try:
                        yield session
                    finally:
                        self._session = None
            else:
                yield self._session
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Call tool using pooled connection"""
        async with self.get_session() as session:
            return await session.call_tool(tool_name, arguments)

# Usage
pool = MCPConnectionPool('localhost', 10100)

# Multiple calls reuse connection
result1 = await pool.call_tool('tool1', {})
result2 = await pool.call_tool('tool2', {})
```

## Solution 5: Monitoring and Debugging

### Enable Debug Logging

```python
import logging

# Enable debug logging for MCP
logging.getLogger('mcp').setLevel(logging.DEBUG)
logging.getLogger('abi_core.abi_mcp').setLevel(logging.DEBUG)

# See detailed session lifecycle
async with client.init_session('localhost', 10100, 'streamable-http') as session:
    # Logs will show:
    # - Connection establishment
    # - Session initialization
    # - Tool calls
    # - Session cleanup
    result = await client.find_agent(session, 'query', ctx={})
```

### Monitor Resource Warnings

```python
import warnings

# Convert ResourceWarnings to exceptions for debugging
warnings.filterwarnings('error', category=ResourceWarning)

try:
    async with client.init_session(...) as session:
        result = await session.call_tool(...)
except ResourceWarning as e:
    logger.error(f'Resource leak detected: {e}')
```

## Best Practices Checklist

### Client Side

- [x] ✅ Use `async with` context managers for sessions
- [x] ✅ Always await session operations
- [x] ✅ Handle exceptions properly
- [x] ✅ Implement retry logic for transient errors
- [x] ✅ Set appropriate timeouts
- [ ] ⚠️ Consider connection pooling for high-frequency operations
- [ ] ⚠️ Monitor resource warnings in development

### Server Side

- [ ] ✅ Set appropriate session timeouts
- [ ] ✅ Return results, don't raise exceptions in tools
- [ ] ✅ Implement proper error handling
- [ ] ✅ Log errors for debugging
- [ ] ✅ Use health checks
- [ ] ⚠️ Monitor memory usage
- [ ] ⚠️ Implement request rate limiting

## Common Pitfalls

### ❌ Pitfall 1: Not Using Context Managers

```python
# BAD - Session never closed
session = await create_session()
result = await session.call_tool('tool', {})
```

```python
# GOOD - Session automatically closed
async with client.init_session(...) as session:
    result = await session.call_tool('tool', {})
```

### ❌ Pitfall 2: Ignoring Exceptions

```python
# BAD - Exception terminates session
@mcp.tool()
async def my_tool(query: str):
    result = execute_query(query)  # May raise exception
    return result
```

```python
# GOOD - Exception handled gracefully
@mcp.tool()
async def my_tool(query: str):
    try:
        result = execute_query(query)
        return {'success': True, 'data': result}
    except Exception as e:
        logger.error(f'Error: {e}')
        return {'success': False, 'error': str(e)}
```

### ❌ Pitfall 3: Timeout Too Short

```python
# BAD - 30 second timeout for 2-minute query
mcp = FastMCP('server', session_timeout=30)
```

```python
# GOOD - Appropriate timeout for operation
mcp = FastMCP('server', session_timeout=300)  # 5 minutes
```

## Troubleshooting

### Issue: "Session terminated" on every call

**Diagnosis:**
```bash
# Check server logs
docker logs semantic-layer-container

# Look for:
# - ResourceWarning messages
# - Unclosed stream warnings
# - Exception stack traces
```

**Solution:**
1. Verify server is using proper context managers
2. Check for unhandled exceptions in tools
3. Increase session timeout if needed

### Issue: Intermittent "Session terminated"

**Diagnosis:**
- Likely a timeout issue
- Check query execution time

**Solution:**
```python
# Increase timeout
mcp = FastMCP('server', session_timeout=600)  # 10 minutes
```

### Issue: Memory leaks (ResourceWarning)

**Diagnosis:**
```python
# Enable warnings
import warnings
warnings.simplefilter('always', ResourceWarning)
```

**Solution:**
- Ensure all context managers are properly closed
- Check for background tasks that aren't awaited
- Review async generator cleanup

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Python Async Context Managers](https://docs.python.org/3/reference/datamodel.html#async-context-managers)

---

**Last Updated:** January 2025  
**ABI-Core Version:** 1.5.11+
