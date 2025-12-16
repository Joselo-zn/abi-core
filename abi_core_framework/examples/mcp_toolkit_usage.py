#!/usr/bin/env python3
"""
Example: Using MCPToolkit for Dynamic MCP Tool Access

This example demonstrates how to use the MCPToolkit class to call
custom MCP tools in a pythonic way.
"""

import asyncio
from abi_core.common.semantic_tools import MCPToolkit


async def example_basic_usage():
    """Example 1: Basic dynamic tool calling"""
    print("=" * 60)
    print("Example 1: Basic Dynamic Tool Calling")
    print("=" * 60)
    
    # Initialize toolkit
    toolkit = MCPToolkit()
    
    # Call a custom tool dynamically
    # This assumes you have a custom MCP tool called "my_custom_tool"
    result = await toolkit.my_custom_tool(
        param1="value1",
        param2=123,
        param3={"nested": "data"}
    )
    
    print(f"Result: {result}")
    print()


async def example_explicit_call():
    """Example 2: Using explicit call method"""
    print("=" * 60)
    print("Example 2: Explicit Call Method")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    # Call using the explicit call method
    result = await toolkit.call(
        "my_custom_tool",
        param1="value1",
        param2=123
    )
    
    print(f"Result: {result}")
    print()


async def example_list_tools():
    """Example 3: Listing available tools"""
    print("=" * 60)
    print("Example 3: Listing Available Tools")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    # List all available tools
    tools = await toolkit.list_tools()
    print(f"Available tools: {tools}")
    print()


async def example_check_tool_exists():
    """Example 4: Checking if a tool exists before calling"""
    print("=" * 60)
    print("Example 4: Check Tool Existence")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    tool_name = "my_custom_tool"
    
    if await toolkit.has_tool(tool_name):
        print(f"✅ Tool '{tool_name}' exists, calling it...")
        result = await toolkit.call(tool_name, param="value")
        print(f"Result: {result}")
    else:
        print(f"❌ Tool '{tool_name}' not found")
    print()


async def example_multiple_tools():
    """Example 5: Calling multiple tools in sequence"""
    print("=" * 60)
    print("Example 5: Multiple Tool Calls")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    # Call multiple tools
    tools_to_call = [
        ("tool1", {"param": "value1"}),
        ("tool2", {"param": "value2"}),
        ("tool3", {"param": "value3"}),
    ]
    
    results = []
    for tool_name, params in tools_to_call:
        if await toolkit.has_tool(tool_name):
            result = await toolkit.call(tool_name, **params)
            results.append((tool_name, result))
            print(f"✅ {tool_name}: {result}")
        else:
            print(f"⚠️ {tool_name}: Not available")
    
    print()


async def example_error_handling():
    """Example 6: Error handling"""
    print("=" * 60)
    print("Example 6: Error Handling")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    try:
        # Try to call a tool that might not exist
        result = await toolkit.nonexistent_tool(param="value")
        
        # Check for errors in response
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Success: {result}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print()


async def example_real_world_scenario():
    """Example 7: Real-world scenario - Data processing pipeline"""
    print("=" * 60)
    print("Example 7: Real-World Data Processing Pipeline")
    print("=" * 60)
    
    toolkit = MCPToolkit()
    
    # Step 1: Fetch data
    print("Step 1: Fetching data...")
    data = await toolkit.fetch_data(
        source="database",
        query="SELECT * FROM users WHERE active=true"
    )
    
    if "error" not in data:
        print(f"✅ Fetched {len(data.get('records', []))} records")
        
        # Step 2: Transform data
        print("Step 2: Transforming data...")
        transformed = await toolkit.transform_data(
            data=data,
            operations=["normalize", "enrich", "validate"]
        )
        
        if "error" not in transformed:
            print(f"✅ Transformed successfully")
            
            # Step 3: Store results
            print("Step 3: Storing results...")
            stored = await toolkit.store_results(
                data=transformed,
                destination="cache",
                ttl=3600
            )
            
            if "error" not in stored:
                print(f"✅ Pipeline completed successfully")
            else:
                print(f"❌ Storage failed: {stored['error']}")
        else:
            print(f"❌ Transformation failed: {transformed['error']}")
    else:
        print(f"❌ Data fetch failed: {data['error']}")
    
    print()


async def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("MCPToolkit Usage Examples")
    print("=" * 60 + "\n")
    
    # Run examples
    await example_basic_usage()
    await example_explicit_call()
    await example_list_tools()
    await example_check_tool_exists()
    await example_multiple_tools()
    await example_error_handling()
    await example_real_world_scenario()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
