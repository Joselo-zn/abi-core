"""
MCP Transport Examples - SSE and Streamable HTTP

This example demonstrates how to use both SSE and Streamable HTTP transports
with the ABI MCP client.
"""

import asyncio
import json
from abi_core.abi_mcp import client
from abi_core.common.types import ServerConfig


async def example_sse_transport():
    """Example using SSE (Server-Sent Events) transport."""
    print("\n=== SSE Transport Example ===\n")
    
    # Configure SSE transport
    config = ServerConfig(
        host="localhost",
        port=10100,
        transport="sse",
        url="http://localhost:10100"
    )
    
    print(f"Connecting via SSE to {config.url}")
    print("Note: Both SSE and Streamable HTTP use the same API")
    
    try:
        # Both transports return (read_stream, write_stream) tuple
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            print("✓ SSE session established")
            
            # Example: Find an agent
            result = await client.find_agent(
                session,
                "Find an agent that can execute trades",
                ctx={"agent_id": "agent://client"}
            )
            
            print(f"✓ Agent found: {result.content[0].text}")
            
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_streamable_http_transport():
    """Example using Streamable HTTP transport."""
    print("\n=== Streamable HTTP Transport Example ===\n")
    
    # Configure Streamable HTTP transport
    config = ServerConfig(
        host="localhost",
        port=10100,
        transport="streamable-http",
        url="http://localhost:10100"
    )
    
    print(f"Connecting via Streamable HTTP to {config.url}")
    print("Note: Uses same API as SSE - returns (read_stream, write_stream)")
    
    try:
        # Same API as SSE - returns (read_stream, write_stream) tuple
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            print("✓ Streamable HTTP session established")
            
            # Example: Find an agent
            result = await client.find_agent(
                session,
                "Find an agent for market analysis",
                ctx={"agent_id": "agent://client"}
            )
            
            print(f"✓ Agent found: {result.content[0].text}")
            
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_dynamic_transport():
    """Example showing dynamic transport selection based on environment."""
    print("\n=== Dynamic Transport Selection ===\n")
    
    import os
    
    # Transport can be configured via environment variable
    transport = os.getenv('MCP_TRANSPORT', 'sse')
    
    config = ServerConfig(
        host=os.getenv('MCP_HOST', 'localhost'),
        port=int(os.getenv('MCP_PORT', '10100')),
        transport=transport,
        url=f"http://{os.getenv('MCP_HOST', 'localhost')}:{os.getenv('MCP_PORT', '10100')}"
    )
    
    print(f"Using transport: {config.transport}")
    print(f"Connecting to: {config.url}")
    
    try:
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            print(f"✓ Session established with {config.transport}")
            
            # Example: List available tools
            tools = await session.list_tools()
            print(f"✓ Available tools: {[tool.name for tool in tools.tools]}")
            
    except Exception as e:
        print(f"✗ Error: {e}")


async def example_recommend_agents():
    """Example using recommend_agents tool with both transports."""
    print("\n=== Recommend Agents Example ===\n")
    
    # Try both transports
    for transport in ['sse', 'streamable-http']:
        print(f"\nUsing {transport} transport:")
        
        try:
            async with client.init_session(
                host="localhost",
                port=10100,
                transport=transport
            ) as session:
                result = await client.recommend_agents(
                    session,
                    task_description="Analyze market trends and execute trades",
                    max_agents=3,
                    ctx={"agent_id": "agent://orchestrator"}
                )
                
                agents = json.loads(result.content[0].text)
                print(f"✓ Recommended agents: {[a['name'] for a in agents]}")
                
        except Exception as e:
            print(f"✗ Error with {transport}: {e}")


async def example_custom_tool():
    """Example using custom tool with transport selection."""
    print("\n=== Custom Tool Example ===\n")
    
    config = ServerConfig(
        host="localhost",
        port=10100,
        transport="sse",  # or "streamable-http"
        url="http://localhost:10100"
    )
    
    try:
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            # Call custom tool
            result = await client.custom_tool(
                session,
                tool_name="check_agent_health",
                ctx={"agent_id": "agent://monitor"},
                payload={"agent_name": "trader"}
            )
            
            print(f"✓ Health check result: {result.content[0].text}")
            
    except Exception as e:
        print(f"✗ Error: {e}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("MCP Transport Examples - SSE and Streamable HTTP")
    print("=" * 60)
    
    # Run examples
    await example_sse_transport()
    await example_streamable_http_transport()
    await example_dynamic_transport()
    await example_recommend_agents()
    await example_custom_tool()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
