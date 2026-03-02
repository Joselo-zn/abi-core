"""
Example: MCP Session Reconnection

This example demonstrates the automatic reconnection feature in ABI-Core v1.5.11+
that handles "Session terminated" errors gracefully.

The implementation follows the MCP specification recommendation for handling
404/session-not-found errors by creating a fresh session and retrying.
"""

import asyncio
from abi_core.abi_mcp import client
from abi_core.common.semantic_tools import MCPToolkit
from abi_core.security.agent_auth import with_agent_context


async def example_1_direct_reconnection():
    """
    Example 1: Using call_tool_with_reconnect() directly
    
    This is the low-level API that provides explicit control over reconnection.
    """
    print("\n" + "="*70)
    print("Example 1: Direct Reconnection API")
    print("="*70)
    
    # Build authentication context
    ctx = with_agent_context(
        agent_id="agent://example",
        tool_name="bigquery_search",
        mcp_method="callTool",
        query="SELECT * FROM large_table"
    )
    
    try:
        # This will automatically reconnect on session termination
        result = await client.call_tool_with_reconnect(
            host="localhost",
            port=10100,
            tool_name="bigquery_search",
            arguments={
                "query": "SELECT * FROM large_table LIMIT 1000",
                "_request_context": ctx
            },
            transport="streamable-http",
            max_attempts=3  # Will retry up to 3 times
        )
        
        print(f"✅ Query completed successfully")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"❌ All retry attempts failed: {e}")


async def example_2_mcp_toolkit():
    """
    Example 2: Using MCPToolkit (Recommended)
    
    MCPToolkit automatically uses reconnection for all tool calls.
    This is the recommended approach for most use cases.
    """
    print("\n" + "="*70)
    print("Example 2: MCPToolkit with Automatic Reconnection")
    print("="*70)
    
    # Initialize toolkit
    toolkit = MCPToolkit()
    
    try:
        # Automatic reconnection is built-in
        result = await toolkit.bigquery_search(
            query="SELECT * FROM large_table LIMIT 1000"
        )
        
        print(f"✅ Query completed successfully")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"❌ Query failed: {e}")


async def example_3_long_running_operation():
    """
    Example 3: Long-running operation that might timeout
    
    Demonstrates how reconnection handles operations that exceed
    the default session timeout.
    """
    print("\n" + "="*70)
    print("Example 3: Long-Running Operation")
    print("="*70)
    
    toolkit = MCPToolkit()
    
    try:
        # This query might take several minutes
        result = await toolkit.bigquery_search(
            query="""
                SELECT 
                    user_id,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount
                FROM transactions
                WHERE date >= '2024-01-01'
                GROUP BY user_id
                HAVING COUNT(*) > 100
                ORDER BY total_amount DESC
            """
        )
        
        print(f"✅ Long query completed successfully")
        print(f"Rows returned: {len(result.get('rows', []))}")
        
    except Exception as e:
        print(f"❌ Long query failed: {e}")


async def example_4_custom_retry_logic():
    """
    Example 4: Custom retry logic with MCPToolkit
    
    For cases where you need more control over retry behavior.
    """
    print("\n" + "="*70)
    print("Example 4: Custom Retry Logic")
    print("="*70)
    
    toolkit = MCPToolkit()
    
    try:
        # Use call_with_retry for custom retry parameters
        result = await toolkit.call_with_retry(
            "bigquery_search",
            max_retries=5,  # More retries for critical operations
            retry_delay=2.0,  # Longer delay between retries
            query="SELECT * FROM critical_data"
        )
        
        print(f"✅ Query with custom retry completed")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"❌ Query failed after custom retries: {e}")


async def example_5_error_handling():
    """
    Example 5: Proper error handling
    
    Demonstrates how to handle different types of errors.
    """
    print("\n" + "="*70)
    print("Example 5: Error Handling")
    print("="*70)
    
    toolkit = MCPToolkit()
    
    try:
        result = await toolkit.bigquery_search(
            query="SELECT * FROM table"
        )
        
        # Check for errors in response
        if isinstance(result, dict) and 'error' in result:
            error_msg = result['error'].lower()
            
            if 'session terminated' in error_msg:
                print("⚠️ Session was terminated (should have been retried automatically)")
            elif 'permission denied' in error_msg:
                print("❌ Permission error (not retryable)")
            elif 'syntax error' in error_msg:
                print("❌ SQL syntax error (not retryable)")
            else:
                print(f"❌ Unknown error: {result['error']}")
        else:
            print(f"✅ Query successful: {result}")
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")


async def example_6_monitoring_retries():
    """
    Example 6: Monitoring retry attempts
    
    Shows how to track retry attempts for debugging.
    """
    print("\n" + "="*70)
    print("Example 6: Monitoring Retries")
    print("="*70)
    
    import logging
    
    # Enable debug logging to see retry attempts
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('abi_core.abi_mcp.client')
    
    toolkit = MCPToolkit()
    
    try:
        # This will log each retry attempt
        result = await toolkit.bigquery_search(
            query="SELECT * FROM table"
        )
        
        print(f"✅ Query completed (check logs for retry details)")
        
    except Exception as e:
        print(f"❌ Query failed: {e}")


async def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("MCP Session Reconnection Examples")
    print("ABI-Core v1.5.11+")
    print("="*70)
    
    # Run examples
    await example_1_direct_reconnection()
    await example_2_mcp_toolkit()
    await example_3_long_running_operation()
    await example_4_custom_retry_logic()
    await example_5_error_handling()
    await example_6_monitoring_retries()
    
    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
