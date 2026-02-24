"""
MCP Session Management Examples

Demonstrates best practices for handling MCP sessions and avoiding
"Session terminated" errors.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from abi_core.abi_mcp import client
from abi_core.common.types import ServerConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_session():
    """Example 1: Basic session management (recommended)"""
    print("\n=== Example 1: Basic Session Management ===\n")
    
    try:
        # Context manager ensures proper cleanup
        async with client.init_session('localhost', 10100, 'streamable-http') as session:
            print("✓ Session established")
            
            # Make tool call
            result = await client.find_agent(
                session,
                "Find an agent for data analysis",
                ctx={"agent_id": "agent://client"}
            )
            
            print(f"✓ Tool call successful: {result.content[0].text[:100]}...")
            
        # Session automatically cleaned up here
        print("✓ Session cleaned up automatically")
        
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_retry_logic():
    """Example 2: Retry logic for transient errors"""
    print("\n=== Example 2: Retry Logic ===\n")
    
    async def call_with_retry(
        tool_name: str,
        arguments: dict,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[Any]:
        """Call tool with automatic retry"""
        
        for attempt in range(max_retries):
            try:
                async with client.init_session('localhost', 10100, 'streamable-http') as session:
                    result = await session.call_tool(tool_name, arguments)
                    print(f"✓ Success on attempt {attempt + 1}")
                    return result
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                # Retry on session errors
                if 'session terminated' in error_msg or 'connection' in error_msg:
                    if attempt < max_retries - 1:
                        print(f"⚠ Retry {attempt + 1}/{max_retries}: {e}")
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                
                # Don't retry other errors
                print(f"✗ Non-retryable error: {e}")
                raise
        
        raise Exception(f'Failed after {max_retries} attempts')
    
    try:
        result = await call_with_retry(
            'find_agent',
            {
                'query': 'Find agent',
                '_request_context': {'agent_id': 'agent://client'}
            }
        )
        print(f"✓ Final result received")
        
    except Exception as e:
        print(f"✗ All retries failed: {e}")


async def example_multiple_calls():
    """Example 3: Multiple calls in single session"""
    print("\n=== Example 3: Multiple Calls in Single Session ===\n")
    
    try:
        async with client.init_session('localhost', 10100, 'streamable-http') as session:
            print("✓ Session established")
            
            # Call 1
            result1 = await client.find_agent(
                session,
                "Find data agent",
                ctx={"agent_id": "agent://client"}
            )
            print(f"✓ Call 1 complete")
            
            # Call 2
            result2 = await client.recommend_agents(
                session,
                "Analyze and visualize data",
                max_agents=3,
                ctx={"agent_id": "agent://client"}
            )
            print(f"✓ Call 2 complete")
            
            # Call 3
            result3 = await client.check_agent_health(
                session,
                "data-agent",
                ctx={"agent_id": "agent://client"}
            )
            print(f"✓ Call 3 complete")
            
        print("✓ All calls completed, session cleaned up")
        
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_error_handling():
    """Example 4: Proper error handling"""
    print("\n=== Example 4: Error Handling ===\n")
    
    try:
        async with client.init_session('localhost', 10100, 'streamable-http') as session:
            print("✓ Session established")
            
            try:
                # This might fail
                result = await client.custom_tool(
                    session,
                    'nonexistent_tool',
                    ctx={"agent_id": "agent://client"},
                    payload={}
                )
                print(f"✓ Tool call successful")
                
            except Exception as tool_error:
                # Handle tool error without terminating session
                print(f"⚠ Tool error (session still alive): {tool_error}")
                
                # Session is still valid, can make another call
                result = await client.find_agent(
                    session,
                    "Find agent",
                    ctx={"agent_id": "agent://client"}
                )
                print(f"✓ Recovery call successful")
                
    except Exception as e:
        print(f"✗ Session error: {e}")


async def example_connection_pool():
    """Example 5: Simple connection pooling"""
    print("\n=== Example 5: Connection Pooling ===\n")
    
    class SimplePool:
        """Simple connection pool for demonstration"""
        
        def __init__(self, host: str, port: int, transport: str = 'streamable-http'):
            self.host = host
            self.port = port
            self.transport = transport
        
        async def call_tool(self, tool_name: str, arguments: dict):
            """Call tool with fresh session each time"""
            async with client.init_session(self.host, self.port, self.transport) as session:
                return await session.call_tool(tool_name, arguments)
    
    try:
        pool = SimplePool('localhost', 10100)
        
        # Multiple calls through pool
        print("Making call 1...")
        result1 = await pool.call_tool(
            'find_agent',
            {
                'query': 'Find agent 1',
                '_request_context': {'agent_id': 'agent://client'}
            }
        )
        print("✓ Call 1 complete")
        
        print("Making call 2...")
        result2 = await pool.call_tool(
            'find_agent',
            {
                'query': 'Find agent 2',
                '_request_context': {'agent_id': 'agent://client'}
            }
        )
        print("✓ Call 2 complete")
        
        print("✓ All pooled calls completed")
        
    except Exception as e:
        print(f"✗ Pool error: {e}")


async def example_timeout_handling():
    """Example 6: Handling timeouts"""
    print("\n=== Example 6: Timeout Handling ===\n")
    
    try:
        # Set timeout for long-running operations
        timeout = 60.0  # 60 seconds
        
        async with client.init_session('localhost', 10100, 'streamable-http') as session:
            print(f"✓ Session established with {timeout}s timeout")
            
            try:
                # Use asyncio.wait_for for timeout
                result = await asyncio.wait_for(
                    client.find_agent(
                        session,
                        "Find agent",
                        ctx={"agent_id": "agent://client"}
                    ),
                    timeout=timeout
                )
                print("✓ Operation completed within timeout")
                
            except asyncio.TimeoutError:
                print(f"⚠ Operation exceeded {timeout}s timeout")
                # Session is still valid, can retry or handle
                
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_debug_logging():
    """Example 7: Debug logging for troubleshooting"""
    print("\n=== Example 7: Debug Logging ===\n")
    
    # Enable debug logging
    logging.getLogger('abi_core.abi_mcp').setLevel(logging.DEBUG)
    logging.getLogger('mcp').setLevel(logging.DEBUG)
    
    try:
        async with client.init_session('localhost', 10100, 'streamable-http') as session:
            # Debug logs will show:
            # - Connection establishment
            # - Session initialization
            # - Tool calls
            # - Session cleanup
            
            result = await client.find_agent(
                session,
                "Find agent",
                ctx={"agent_id": "agent://client"}
            )
            
        print("✓ Check logs above for detailed session lifecycle")
        
    except Exception as e:
        print(f"✗ Error (check logs): {e}")
    finally:
        # Reset logging
        logging.getLogger('abi_core.abi_mcp').setLevel(logging.INFO)
        logging.getLogger('mcp').setLevel(logging.INFO)


async def main():
    """Run all examples"""
    print("=" * 60)
    print("MCP Session Management Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Session Management", example_basic_session),
        ("Retry Logic", example_retry_logic),
        ("Multiple Calls", example_multiple_calls),
        ("Error Handling", example_error_handling),
        ("Connection Pooling", example_connection_pool),
        ("Timeout Handling", example_timeout_handling),
        ("Debug Logging", example_debug_logging),
    ]
    
    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            print(f"\n✗ Example '{name}' failed: {e}")
        
        # Pause between examples
        await asyncio.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. Always use 'async with' for sessions")
    print("2. Implement retry logic for transient errors")
    print("3. Handle errors without terminating session")
    print("4. Use timeouts for long operations")
    print("5. Enable debug logging for troubleshooting")


if __name__ == "__main__":
    asyncio.run(main())
