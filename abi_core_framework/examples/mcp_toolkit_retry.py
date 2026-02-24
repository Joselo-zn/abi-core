"""
MCPToolkit Retry Logic Example

Demonstrates how to use MCPToolkit with automatic retry for handling
"Session terminated" errors and other transient failures.
"""

import asyncio
import logging
from abi_core.common.semantic_tools import MCPToolkit
from abi_core.common.utils import get_mcp_server_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_call():
    """Example 1: Basic MCPToolkit call"""
    print("\n=== Example 1: Basic Call ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        # Basic call without retry
        result = await toolkit.call(
            "find_agent",
            query="Find an agent for data analysis"
        )
        
        if 'error' in result:
            print(f"✗ Error: {result['error']}")
        else:
            print(f"✓ Success: {result}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_call_with_retry():
    """Example 2: Call with automatic retry"""
    print("\n=== Example 2: Call with Retry ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        # Call with automatic retry (up to 3 attempts)
        result = await toolkit.call_with_retry(
            "find_agent",
            max_retries=3,
            retry_delay=1.0,
            query="Find an agent for data analysis"
        )
        
        if 'error' in result:
            print(f"✗ Error after retries: {result['error']}")
        else:
            print(f"✓ Success: {result}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_long_running_operation():
    """Example 3: Long-running operation with retry"""
    print("\n=== Example 3: Long-Running Operation ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        # Simulate a long-running BigQuery operation
        # This is more likely to hit "Session terminated" errors
        result = await toolkit.call_with_retry(
            "semantic_bigquery_search",
            max_retries=5,  # More retries for long operations
            retry_delay=2.0,  # Longer delay between retries
            query="SELECT * FROM large_table WHERE date > '2024-01-01'"
        )
        
        if 'error' in result:
            print(f"✗ Query failed: {result['error']}")
        else:
            print(f"✓ Query succeeded")
            print(f"  Rows returned: {len(result.get('data', []))}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_pythonic_syntax():
    """Example 4: Pythonic syntax with retry"""
    print("\n=== Example 4: Pythonic Syntax ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        # Pythonic attribute access
        # Note: This uses call() internally, not call_with_retry()
        result = await toolkit.find_agent(
            query="Find an agent for data visualization"
        )
        
        if 'error' in result:
            print(f"✗ Error: {result['error']}")
        else:
            print(f"✓ Success: {result}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_custom_retry_logic():
    """Example 5: Custom retry logic"""
    print("\n=== Example 5: Custom Retry Logic ===\n")
    
    toolkit = MCPToolkit()
    
    async def call_with_custom_retry(tool_name: str, **kwargs):
        """Custom retry logic with specific error handling"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            result = await toolkit.call(tool_name, **kwargs)
            
            # Check for specific errors
            if isinstance(result, dict) and 'error' in result:
                error = result['error']
                
                # Only retry on session errors
                if 'session terminated' in error.lower():
                    if attempt < max_attempts - 1:
                        wait_time = 2 ** attempt  # Exponential: 1s, 2s, 4s
                        print(f"⚠ Session error, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"✗ Max retries reached")
                        return result
                else:
                    # Non-retryable error
                    print(f"✗ Non-retryable error: {error}")
                    return result
            else:
                # Success
                return result
        
        return {"error": "Failed after all retries"}
    
    try:
        result = await call_with_custom_retry(
            "find_agent",
            query="Find agent"
        )
        
        if 'error' in result:
            print(f"✗ Final error: {result['error']}")
        else:
            print(f"✓ Success: {result}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_list_tools():
    """Example 6: List available tools"""
    print("\n=== Example 6: List Available Tools ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        tools = await toolkit.list_tools()
        
        if tools:
            print(f"✓ Available tools ({len(tools)}):")
            for tool in tools:
                print(f"  - {tool}")
        else:
            print("✗ No tools available or error listing tools")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_check_tool_exists():
    """Example 7: Check if tool exists before calling"""
    print("\n=== Example 7: Check Tool Exists ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        tool_name = "find_agent"
        
        if await toolkit.has_tool(tool_name):
            print(f"✓ Tool '{tool_name}' exists")
            
            # Call with retry
            result = await toolkit.call_with_retry(
                tool_name,
                query="Find agent"
            )
            
            if 'error' not in result:
                print(f"✓ Tool call successful")
            else:
                print(f"✗ Tool call failed: {result['error']}")
        else:
            print(f"✗ Tool '{tool_name}' not found")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


async def example_error_handling():
    """Example 8: Comprehensive error handling"""
    print("\n=== Example 8: Comprehensive Error Handling ===\n")
    
    toolkit = MCPToolkit()
    
    try:
        result = await toolkit.call_with_retry(
            "find_agent",
            max_retries=3,
            retry_delay=1.0,
            query="Find agent"
        )
        
        # Check result type
        if not isinstance(result, dict):
            print(f"⚠ Unexpected result type: {type(result)}")
            return
        
        # Check for errors
        if 'error' in result:
            error = result['error']
            
            # Categorize error
            if 'session terminated' in error.lower():
                print(f"✗ Session error (after retries): {error}")
                print("  Suggestion: Increase timeout or check server health")
            elif 'timeout' in error.lower():
                print(f"✗ Timeout error: {error}")
                print("  Suggestion: Increase timeout or optimize query")
            elif 'connection' in error.lower():
                print(f"✗ Connection error: {error}")
                print("  Suggestion: Check network and server status")
            else:
                print(f"✗ Other error: {error}")
        else:
            print(f"✓ Success: {result}")
            
    except Exception as e:
        print(f"✗ Unhandled exception: {e}")
        print(f"  Type: {type(e).__name__}")


async def main():
    """Run all examples"""
    print("=" * 60)
    print("MCPToolkit Retry Logic Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Call", example_basic_call),
        ("Call with Retry", example_call_with_retry),
        ("Long-Running Operation", example_long_running_operation),
        ("Pythonic Syntax", example_pythonic_syntax),
        ("Custom Retry Logic", example_custom_retry_logic),
        ("List Tools", example_list_tools),
        ("Check Tool Exists", example_check_tool_exists),
        ("Error Handling", example_error_handling),
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
    print("1. Use call_with_retry() for operations prone to transient errors")
    print("2. Adjust max_retries and retry_delay based on operation type")
    print("3. Long-running operations need more retries and longer delays")
    print("4. Check for 'error' key in results for error handling")
    print("5. Use has_tool() to verify tool exists before calling")


if __name__ == "__main__":
    asyncio.run(main())
