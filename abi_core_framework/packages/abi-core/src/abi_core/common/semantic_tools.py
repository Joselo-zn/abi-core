"""
Semantic layer tools for agent discovery and coordination.

This module provides LangChain tools that agents can use to interact with
the semantic layer for discovering other agents, checking capabilities, and
monitoring health.
"""

import json
import os
from typing import Optional, List, Dict, Any, Callable

from abi_core.common.utils import get_mcp_server_config, abi_logging
from abi_core.abi_mcp import client
from abi_core.security.agent_auth import build_semantic_context_from_card

from langchain.tools import tool
from a2a.types import AgentCard

AGENT_CARD_PATH = os.getenv('AGENT_CARD')
_mcp_config = get_mcp_server_config()


class MCPToolkit:
    """
    Dynamic MCP tool caller that allows pythonic access to custom MCP tools.
    
    This class provides a flexible interface for calling any MCP tool dynamically
    using attribute access or direct calls.
    
    Usage:
        # Initialize toolkit
        toolkit = MCPToolkit()
        
        # Call tools dynamically
        result = await toolkit.my_custom_tool(param1="value", param2=123)
        
        # Or use call method
        result = await toolkit.call("my_custom_tool", param1="value", param2=123)
        
        # Check if tool exists
        if toolkit.has_tool("my_custom_tool"):
            result = await toolkit.my_custom_tool()
    """
    
    def __init__(self, agent_card_path: str = None, mcp_config = None):
        """
        Initialize the MCP toolkit.
        
        Args:
            agent_card_path: Path to agent card (defaults to AGENT_CARD env var)
            mcp_config: MCP server configuration (defaults to global config)
        """
        self.agent_card_path = agent_card_path or AGENT_CARD_PATH
        self.mcp_config = mcp_config or _mcp_config
        self._available_tools = None
    
    async def call(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a custom MCP tool with keyword arguments.
        
        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Tool-specific parameters
        
        Returns:
            Dictionary with the tool's response or error information
        
        Example:
            result = await toolkit.call("my_tool", param1="value", param2=123)
        """
        async with client.init_session(
            self.mcp_config.host,
            self.mcp_config.port,
            self.mcp_config.transport
        ) as mcp_session:
            abi_logging(f"[🔧] Calling MCP tool '{tool_name}' with args: {kwargs}")
            
            # Build context for authentication
            context = build_semantic_context_from_card(
                self.agent_card_path,
                tool_name=tool_name,
                query=json.dumps(kwargs)
            )

            try:
                mcp_response = await client.custom_tool(
                    mcp_session,
                    tool_name,
                    context,
                    kwargs
                )
                
                if hasattr(mcp_response, 'content') and mcp_response.content:
                    try:
                        # Parse response content
                        if isinstance(mcp_response.content, list) and mcp_response.content:
                            result = json.loads(mcp_response.content[0].text)
                        else:
                            result = mcp_response.content
                        
                        abi_logging(f"[✅] Tool '{tool_name}' executed successfully")
                        return result if result else {}
                        
                    except json.JSONDecodeError as e:
                        abi_logging(f'[❌] Error parsing response from {tool_name}: {e}')
                        return {"error": f"JSON parsing error: {str(e)}"}
                    except Exception as e:
                        abi_logging(f'[❌] Error processing response from {tool_name}: {e}')
                        return {"error": str(e)}
                else:
                    abi_logging(f'[⚠️] No response from tool {tool_name}')
                    return {"error": "No response from tool"}
                    
            except Exception as e:
                abi_logging(f'[❌] Error calling tool {tool_name}: {e}')
                return {"error": f"Tool execution error: {str(e)}"}
    
    async def list_tools(self) -> List[str]:
        """
        List all available MCP tools from the server.
        
        Returns:
            List of available tool names
        """
        try:
            async with client.init_session(
                self.mcp_config.host,
                self.mcp_config.port,
                self.mcp_config.transport
            ) as mcp_session:
                # List tools from MCP server
                tools_response = await mcp_session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                self._available_tools = tool_names
                abi_logging(f"[📋] Available MCP tools: {', '.join(tool_names)}")
                return tool_names
        except Exception as e:
            abi_logging(f'[❌] Error listing tools: {e}')
            return []
    
    async def has_tool(self, tool_name: str) -> bool:
        """
        Check if a specific tool is available.
        
        Args:
            tool_name: Name of the tool to check
        
        Returns:
            True if tool exists, False otherwise
        """
        if self._available_tools is None:
            await self.list_tools()
        return tool_name in (self._available_tools or [])
    
    def __getattr__(self, tool_name: str) -> Callable:
        """
        Enable dynamic tool access via attribute syntax.
        
        Args:
            tool_name: Name of the tool to call
        
        Returns:
            Async callable that executes the tool
        
        Example:
            result = await toolkit.my_custom_tool(param1="value")
        """
        # Avoid infinite recursion for internal attributes
        if tool_name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{tool_name}'")
        
        async def tool_caller(**kwargs):
            return await self.call(tool_name, **kwargs)
        
        # Set function name for better debugging
        tool_caller.__name__ = tool_name
        tool_caller.__doc__ = f"Call MCP tool '{tool_name}' with keyword arguments"
        
        return tool_caller
    
    def __repr__(self) -> str:
        """String representation of the toolkit."""
        tools_info = f"{len(self._available_tools)} tools" if self._available_tools else "tools not loaded"
        return f"MCPToolkit(host={self.mcp_config.host}, port={self.mcp_config.port}, {tools_info})"


# Global toolkit instance for easy access
mcp_toolkit = MCPToolkit()

@tool
async def custom_call(tool_name: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call a custom MCP tool with arbitrary payload.
    
    This is a LangChain tool wrapper that allows calling any custom MCP tool
    that users have implemented in their semantic layer.
    
    Args:
        tool_name: Name of the custom MCP tool to call
        payload: Optional dictionary with tool-specific parameters
    
    Returns:
        Dictionary with the tool's response or error information
    
    Example:
        # Call a custom tool
        result = await custom_call(
            tool_name="my_custom_tool",
            payload={"param1": "value1", "param2": 123}
        )
    
    Note:
        For more pythonic access, consider using MCPToolkit directly:
        
        toolkit = MCPToolkit()
        result = await toolkit.my_custom_tool(param1="value1", param2=123)
    """
    if payload is None:
        payload = {}
    
    # Use the global toolkit instance
    return await mcp_toolkit.call(tool_name, **payload)

@tool
async def tool_find_agent(query: str) -> Optional[AgentCard]:
    """Find an Angent to complete especific task"""
    
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        abi_logging(f"[🔍] Searching for agent matching query {query}")
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="find_agent",
            query=query
        )

        mcp_response = await client.find_agent(mcp_session, query, context)
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                if isinstance(mcp_response.content, list) and mcp_response.content:
                    agent_card_json = json.loads(mcp_response.content[0].text)
                else:
                    agent_card_json = mcp_response.content
                
                if agent_card_json:
                    return AgentCard(**agent_card_json)
                else:
                    return None
            except Exception as e:
                abi_logging(f'[X] Error parsing agent card {e}')
        else:
            abi_logging(f'No Agents found')
            return None

@tool
async def tool_list_agents(query: str) -> List[AgentCard]:
    """List Agents that can complete especific task"""
    
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="list_agents",
            query=query
        )
        resource = f'resource://agent_cards/list/{query}'
        abi_logging(f"[🔍] Listing agents matching query {query}")
        mcp_response = await client.find_resource(mcp_session, resource)
        agents = []
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                for content in mcp_response.content:
                    agent_card_json = json.loads(content.text)
                    agents.append(AgentCard(**agent_card_json))
                return agents
            except Exception as e:
                abi_logging(f'[X] Error parsing agent cards {e}')
        else:
            abi_logging(f'No Agents found')
            return agents


@tool
async def tool_recommend_agents(
    task_description: str,
    max_agents: int = 3
) -> List[Dict[str, Any]]:
    """Recommend multiple agents for a complex task.
    
    Args:
        task_description: Description of the task requiring multiple agents
        max_agents: Maximum number of agents to recommend (default: 3)
    
    Returns:
        List of recommended agents with relevance scores and confidence levels
    """
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        abi_logging(f"[🔍] Recommending agents for: {task_description}")
        
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="recommend_agents",
            query=task_description
        )
        
        mcp_response = await client.recommend_agents(
            mcp_session,
            task_description,
            max_agents,
            context
        )
        
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                if isinstance(mcp_response.content, list) and mcp_response.content:
                    recommendations = json.loads(mcp_response.content[0].text)
                else:
                    recommendations = mcp_response.content
                
                abi_logging(f"[✅] Found {len(recommendations)} recommendations")
                return recommendations if recommendations else []
            except Exception as e:
                abi_logging(f'[X] Error parsing recommendations: {e}')
                return []
        else:
            abi_logging(f'No recommendations found')
            return []


@tool
async def tool_check_agent_capability(
    agent_name: str,
    required_tasks: List[str]
) -> Dict[str, Any]:
    """Check if an agent has specific capabilities.
    
    Args:
        agent_name: Name of the agent to check
        required_tasks: List of required task names
    
    Returns:
        Capability check result with supported/missing tasks
    """
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        abi_logging(f"[🔍] Checking capabilities for: {agent_name}")
        
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="check_agent_capability",
            query=agent_name
        )
        
        mcp_response = await client.check_agent_capability(
            mcp_session,
            agent_name,
            required_tasks,
            context
        )
        
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                if isinstance(mcp_response.content, list) and mcp_response.content:
                    result = json.loads(mcp_response.content[0].text)
                else:
                    result = mcp_response.content
                
                abi_logging(f"[✅] Capability check complete")
                return result if result else {}
            except Exception as e:
                abi_logging(f'[X] Error parsing capability check: {e}')
                return {"error": str(e)}
        else:
            abi_logging(f'No capability data found')
            return {}


@tool
async def tool_check_agent_health(agent_name: str) -> Dict[str, Any]:
    """Check if an agent is online and responding.
    
    Args:
        agent_name: Name of the agent to check
    
    Returns:
        Health status with response time and status code
    """
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        abi_logging(f"[🏥] Checking health for: {agent_name}")
        
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="check_agent_health",
            query=agent_name
        )
        
        mcp_response = await client.check_agent_health(
            mcp_session,
            agent_name,
            context
        )
        
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                if isinstance(mcp_response.content, list) and mcp_response.content:
                    result = json.loads(mcp_response.content[0].text)
                else:
                    result = mcp_response.content
                
                abi_logging(f"[✅] Health check complete: {result.get('status', 'unknown')}")
                return result if result else {}
            except Exception as e:
                abi_logging(f'[X] Error parsing health check: {e}')
                return {"error": str(e)}
        else:
            abi_logging(f'No health data found')
            return {}


@tool
async def tool_register_agent(agent_card_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new agent in the semantic layer.
    
    Args:
        agent_card_dict: Complete agent card dictionary with auth credentials.
                        Must include: id, name, auth (with method, key_id, shared_secret),
                        description, supportedTasks, skills, etc.
    
    Returns:
        Registration result with success status and agent info
    
    Security:
        - Requires HMAC authentication via agent_card.auth
        - Requires authorization via OPA policy
        - Only trusted agents (orchestrator, planner, observer) or agents with
          'register_agents' permission can register new agents
    
    Example:
        agent_card = {
            "id": "agent://new_agent",
            "name": "new_agent",
            "description": "New agent description",
            "auth": {
                "method": "hmac_sha256",
                "key_id": "agent://new_agent-default",
                "shared_secret": "generated_secret_key"
            },
            "supportedTasks": ["task1", "task2"],
            "skills": [...]
        }
        result = await tool_register_agent(agent_card)
    """
    async with client.init_session(
        _mcp_config.host,
        _mcp_config.port,
        _mcp_config.transport
    ) as mcp_session:
        agent_name = agent_card_dict.get('name', 'unknown')
        abi_logging(f"[📝] Registering new agent: {agent_name}")
        
        context = build_semantic_context_from_card(
            AGENT_CARD_PATH,
            tool_name="register_agent",
            query=f"register {agent_name}"
        )
        
        mcp_response = await client.register_agent(
            mcp_session,
            agent_card_dict,
            context
        )
        
        if hasattr(mcp_response, 'content') and mcp_response.content:
            try:
                if isinstance(mcp_response.content, list) and mcp_response.content:
                    result = json.loads(mcp_response.content[0].text)
                else:
                    result = mcp_response.content
                
                if result.get('success'):
                    abi_logging(f"[✅] Agent registered: {result.get('agent_name')}")
                else:
                    abi_logging(f"[❌] Registration failed: {result.get('error')}")
                
                return result if result else {"success": False, "error": "Empty response"}
            except Exception as e:
                abi_logging(f'[X] Error parsing registration result: {e}')
                return {"success": False, "error": str(e)}
        else:
            abi_logging(f'No registration response')
            return {"success": False, "error": "No response from semantic layer"}
