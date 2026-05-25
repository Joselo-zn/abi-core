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
from abi_core.common.service_card import ServiceCard
from abi_core.common.agent_card_loader import build_agent_card, get_agent_url

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
        # Initialize toolkit with agent card (agents)
        toolkit = MCPToolkit()
        
        # Initialize toolkit with service card (services like webapp)
        from abi_core.common.service_card import ServiceCard
        card = ServiceCard.from_file("service_cards/webapp.json")
        toolkit = MCPToolkit(service_card=card)
        
        # Call tools dynamically
        result = await toolkit.my_custom_tool(param1="value", param2=123)
        
        # Or use call method
        result = await toolkit.call("my_custom_tool", param1="value", param2=123)
        
        # Check if tool exists
        if toolkit.has_tool("my_custom_tool"):
            result = await toolkit.my_custom_tool()
    """
    
    def __init__(self, agent_card_path: str = None, mcp_config = None, service_card: ServiceCard = None):
        """
        Initialize the MCP toolkit.
        
        Args:
            agent_card_path: Path to agent card (defaults to AGENT_CARD env var)
            mcp_config: MCP server configuration (defaults to global config)
            service_card: ServiceCard instance for non-agent services (takes priority over agent_card_path)
        """
        self.agent_card_path = agent_card_path or AGENT_CARD_PATH
        self.mcp_config = mcp_config or _mcp_config
        self.service_card = service_card
        self._available_tools = None
    
    async def call_with_retry(
        self,
        tool_name: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call a custom MCP tool with automatic retry on transient errors.
        
        This method automatically retries on "Session terminated" and connection errors,
        which are common with long-running operations or network issues.
        
        Args:
            tool_name: Name of the MCP tool to call
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Base delay between retries in seconds (default: 1.0)
                        Uses exponential backoff: delay * (attempt + 1)
            **kwargs: Tool-specific parameters
        
        Returns:
            Dictionary with the tool's response or error information
        
        Example:
            # Retry up to 3 times with exponential backoff
            result = await toolkit.call_with_retry(
                "bigquery_search",
                max_retries=3,
                retry_delay=2.0,
                query="SELECT * FROM table"
            )
        """
        import asyncio
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await self.call(tool_name, **kwargs)
                
                # Check if result contains a retryable error
                if isinstance(result, dict) and 'error' in result:
                    error_msg = str(result['error']).lower()
                    
                    # Retry on session/connection errors
                    if any(keyword in error_msg for keyword in [
                        'session terminated',
                        'session error',
                        'connection',
                        'timeout'
                    ]):
                        last_error = result['error']
                        
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (attempt + 1)
                            abi_logging(
                                f"[⚠️] Retryable error on attempt {attempt + 1}/{max_retries}: "
                                f"{result['error']}. Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            abi_logging(f"[❌] Max retries ({max_retries}) reached for tool '{tool_name}'")
                            return result
                    else:
                        # Non-retryable error, return immediately
                        return result
                else:
                    # Success
                    if attempt > 0:
                        abi_logging(f"[✅] Tool '{tool_name}' succeeded on attempt {attempt + 1}")
                    return result
                    
            except Exception as e:
                last_error = str(e)
                error_msg = str(e).lower()
                
                # Retry on session/connection exceptions
                if any(keyword in error_msg for keyword in [
                    'session terminated',
                    'session error',
                    'connection',
                    'timeout'
                ]):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        abi_logging(
                            f"[⚠️] Exception on attempt {attempt + 1}/{max_retries}: "
                            f"{e}. Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        abi_logging(f"[❌] Max retries ({max_retries}) reached for tool '{tool_name}'")
                        return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
                else:
                    # Non-retryable exception
                    abi_logging(f"[❌] Non-retryable exception: {e}")
                    return {"error": str(e)}
        
        # Should not reach here, but just in case
        return {"error": f"Failed after {max_retries} attempts: {last_error}"}
    
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
        try:
            async with client.init_session(
                self.mcp_config.host,
                self.mcp_config.port,
                self.mcp_config.transport
            ) as mcp_session:
                abi_logging(f"[🔧] Calling MCP tool '{tool_name}' with args: {kwargs}")
                
                # Build context: ServiceCard takes priority over agent card path
                if self.service_card is not None:
                    context = self.service_card.build_context(
                        tool_name=tool_name,
                        query=json.dumps(kwargs),
                    )
                else:
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
                    
                    # Debug: log raw response structure
                    _has = hasattr(mcp_response, 'content')
                    _ctype = type(mcp_response.content).__name__ if _has else 'N/A'
                    _clen = len(mcp_response.content) if _has and mcp_response.content else 0
                    abi_logging(f"[📡] MCP response for '{tool_name}': has_content={_has}, type={_ctype}, len={_clen}")
                    if _has and mcp_response.content and isinstance(mcp_response.content, list) and hasattr(mcp_response.content[0], 'text'):
                        abi_logging(f"[📡] Response text: {mcp_response.content[0].text[:300]}")

                    if hasattr(mcp_response, 'content') and mcp_response.content:
                        try:
                            # Parse response content
                            if isinstance(mcp_response.content, list) and mcp_response.content:
                                result = json.loads(mcp_response.content[0].text)
                            else:
                                result = mcp_response.content
                            
                            abi_logging(f"[✅] Tool '{tool_name}' executed successfully")
                            return result if result is not None else {}
                            
                        except json.JSONDecodeError as e:
                            abi_logging(f'[❌] Error parsing response from {tool_name}: {e}')
                            return {"error": f"JSON parsing error: {str(e)}"}
                        except Exception as e:
                            abi_logging(f'[❌] Error processing response from {tool_name}: {e}')
                            return {"error": str(e)}
                    else:
                        abi_logging(f'[📡] Tool {tool_name}: empty content (no results)')
                        return {}
                        
                except Exception as e:
                    abi_logging(f'[❌] Error calling tool {tool_name}: {e}')
                    return {"error": f"Tool execution error: {str(e)}"}
                    
        except Exception as e:
            # Session-level error (connection, initialization, etc.)
            abi_logging(f'[❌] Session error calling tool {tool_name}: {e}')
            return {"error": f"Session error: {str(e)}"}
    
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

    async def list_tools_detailed(self) -> List[Dict[str, Any]]:
        """List all MCP tools with name, description, and input schema.

        Returns:
            List of dicts with ``name``, ``description``, ``inputSchema``.
        """
        try:
            async with client.init_session(
                self.mcp_config.host,
                self.mcp_config.port,
                self.mcp_config.transport,
            ) as mcp_session:
                resp = await mcp_session.list_tools()
                tools = []
                for t in resp.tools:
                    tools.append({
                        "name": t.name,
                        "description": getattr(t, "description", "") or "",
                        "inputSchema": getattr(t, "inputSchema", {}) or {},
                    })
                abi_logging(f"[📋] Listed {len(tools)} MCP tools (detailed)")
                return tools
        except Exception as e:
            abi_logging(f"[❌] Error listing tools (detailed): {e}")
            return []

    async def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search MCP tools whose name or description matches *query*.

        Simple keyword match — returns tools where any word in *query*
        appears in the tool name or description (case-insensitive).

        Args:
            query: Free-text description of the capability needed.

        Returns:
            List of matching tool dicts (name, description, inputSchema).
        """
        all_tools = await self.list_tools_detailed()
        if not all_tools:
            return []

        keywords = [w.lower() for w in query.split() if len(w) > 2]
        if not keywords:
            return all_tools

        matches = []
        for t in all_tools:
            haystack = f"{t['name']} {t['description']}".lower()
            if any(kw in haystack for kw in keywords):
                matches.append(t)

        abi_logging(f"[🔍] search_tools('{query}'): {len(matches)}/{len(all_tools)} matches")
        return matches
    
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
                    # Skip service cards and tool cards — they are not agents
                    if agent_card_json.get("service_id") or agent_card_json.get("service_type"):
                        abi_logging(f"[⏭️] Skipping service card: {agent_card_json.get('name', 'unknown')}")
                        return None
                    if not agent_card_json.get("capabilities"):
                        abi_logging(f"[⏭️] Skipping non-agent card (no capabilities): {agent_card_json.get('name', 'unknown')}")
                        return None
                    card, _meta = build_agent_card(agent_card_json)
                    return card
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
                    # Skip service/tool cards
                    if agent_card_json.get("service_id") or agent_card_json.get("service_type"):
                        continue
                    if not agent_card_json.get("capabilities"):
                        continue
                    agents.append(build_agent_card(agent_card_json)[0])
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

    Uses AbiAgent.check_health() — no MCP call needed.
    Requires the agent's URL, which is looked up from the semantic layer.

    Args:
        agent_name: Name of the agent to check

    Returns:
        Health status with response_time_ms and status_code
    """
    # Find agent card to get URL
    agent_card = await tool_find_agent.ainvoke(agent_name)
    if not agent_card:
        return {"agent": agent_name, "status": "not_found", "error": "Agent not found"}

    agent_url = (
        agent_card.get("url", "")
        if isinstance(agent_card, dict)
        else get_agent_url(agent_card)
    )
    if not agent_url:
        return {"agent": agent_name, "status": "error", "error": "No URL in agent card"}

    from abi_core.agent.agent import AbiAgent

    return await AbiAgent.check_health(agent_url, agent_name)


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
                    raw_text = mcp_response.content[0].text
                    if not raw_text or raw_text.strip() in ("", "None", "null"):
                        abi_logging(f'[⚠️] Empty text in MCP response for register_agent')
                        return {"success": False, "error": "Empty response from semantic layer (access may have been denied)"}
                    result = json.loads(raw_text)
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


@tool
async def tool_search_tools(query: str) -> List[Dict[str, Any]]:
    """Search the ToolRegistry for tools matching a task description.

    Uses semantic similarity via the semantic layer's search_tool_registry
    MCP tool.  Returns full ToolCard specs including access_scope.

    Args:
        query: Description of the capability or task needed.

    Returns:
        List of matching tools with name, description, score, and full spec.
    """
    return await mcp_toolkit.call("search_tool_registry", query=query, max_results=5)
