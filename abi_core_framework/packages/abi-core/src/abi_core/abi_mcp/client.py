import asyncio
import json
import os
import click
import logging

from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, ReadResourceResult

logger = logging.getLogger(__name__)


@asynccontextmanager
async def init_session(host, port, transport):
    """Initializes and manages an MCP ClientSession based on the specified transport.

    This asynchronous context manager establishes a connection to an MCP server
    using Server-Sent Events (SSE) transport.
    It handles the setup and teardown of the connection and yields an active
    `ClientSession` object ready for communication.

    Args:
        host: The hostname or IP address of the MCP server (used for SSE).
        port: The port number of the MCP server (used for SSE).
        transport: The communication transport to use ('sse').

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If an unsupported transport type is provided.
        Exception: Other potential exceptions during client initialization or
                   session setup.
    """

    if transport != 'sse':
        logger.error(f'Unsupported Transport type {transport}')
        raise ValueError(
            f"Unsupported transport type: {transport}. Must be 'sse'"
        )
    
    url = f'http://{host}:{port}/sse'
    logger.info(f'Connecting to MCP server at {url}')
    
    try:
        async with sse_client(url) as (read_stream, write_stream):
            logger.info('SSE connection established')
            try:
                async with ClientSession(
                    read_stream=read_stream,
                    write_stream=write_stream,
                ) as session:
                    logger.info('SSE Client Session Initializing...')
                    await session.initialize()
                    logger.info('SSE Client Session Initialized Successfully')
                    yield session
            except Exception as e:
                logger.error(f'Error initializing ClientSession: {e}', exc_info=True)
                raise
    except Exception as e:
        logger.error(f'Error connecting to SSE server at {url}: {e}', exc_info=True)
        raise

async def find_agent(session: ClientSession, query: str, ctx) -> CallToolResult:
    """Call the tool 'find_agent' tool on the connected MCP server.

    Args:
        session: The active ClienteSession.
        query: The natural language query to send to the 'find_agent' tool.

    Returns:
        The result of the tool call.
    """

    return await session.call_tool(
        name='find_agent',
        arguments={
            'query': query,
            '_request_context':ctx
        },
    )

async def find_resource(session: ClientSession, resource: str) -> ReadResourceResult:
    """Reads a resource from the connected MCP server.

    Args:
        session: The active ClientSession.
        resource: The URI of the resource to read (e.g., 'resource://agent_cards/list').

    Returns:
        The result of the resource read operation.
    """
    logger.info(f'Reading resource: {resource}')
    return await session.read_resource(resource)


async def recommend_agents(
    session: ClientSession,
    task_description: str,
    max_agents: int,
    ctx: dict
) -> CallToolResult:
    """Call the 'recommend_agents' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        task_description: Description of the task requiring multiple agents.
        max_agents: Maximum number of agents to recommend.
        ctx: Request context for authentication.

    Returns:
        The result of the tool call.
    """
    return await session.call_tool(
        name='recommend_agents',
        arguments={
            'task_description': task_description,
            'max_agents': max_agents,
            '_request_context': ctx
        },
    )


async def check_agent_capability(
    session: ClientSession,
    agent_name: str,
    required_tasks: list,
    ctx: dict
) -> CallToolResult:
    """Call the 'check_agent_capability' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        agent_name: Name of the agent to check.
        required_tasks: List of required task names.
        ctx: Request context for authentication.

    Returns:
        The result of the tool call.
    """
    return await session.call_tool(
        name='check_agent_capability',
        arguments={
            'agent_name': agent_name,
            'required_tasks': required_tasks,
            '_request_context': ctx
        },
    )


async def check_agent_health(
    session: ClientSession,
    agent_name: str,
    ctx: dict
) -> CallToolResult:
    """Call the 'check_agent_health' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        agent_name: Name of the agent to check.
        ctx: Request context for authentication.

    Returns:
        The result of the tool call.
    """
    return await session.call_tool(
        name='check_agent_health',
        arguments={
            'agent_name': agent_name,
            '_request_context': ctx
        },
    )


async def register_agent(
    session: ClientSession,
    agent_card: dict,
    ctx: dict
) -> CallToolResult:
    """Call the 'register_agent' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        agent_card: Complete agent card dictionary with auth credentials.
        ctx: Request context for authentication.

    Returns:
        The result of the tool call with registration status.
    """
    return await session.call_tool(
        name='register_agent',
        arguments={
            'agent_card': agent_card,
            '_request_context': ctx
        },
    )

async def custom_tool(
    session: ClientSession,
    tool_name: str,
    ctx: dict,
    payload: dict = None
) -> CallToolResult:
    """Call custom tool on the connected MCP server.
    
    Args:
        session: The active ClientSession.
        tool_name: The name of the tool to call.
        ctx: Request context for authentication.
        payload: Optional payload to be used by the tool (default: None).

    Returns:
        The result of the tool call.
    """
    if payload is None:
        payload = {}
    
    # Merge payload with request context
    arguments = {
        '_request_context': ctx,
        **payload  # Unpack payload directly into arguments
    }
    
    logger.info(f'Calling custom tool: {tool_name}')
    return await session.call_tool(
        name=tool_name,
        arguments=arguments,
    )
