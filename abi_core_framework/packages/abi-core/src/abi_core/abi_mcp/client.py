import asyncio
import json
import os
import click
import logging

from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, ReadResourceResult

logger = logging.getLogger(__name__)


def _is_session_terminated_error(error: Exception) -> bool:
    """Check if an error indicates a terminated session.
    
    Args:
        error: The exception to check.
        
    Returns:
        True if the error indicates a terminated session, False otherwise.
    """
    error_msg = str(error).lower()
    return (
        'session terminated' in error_msg or
        '404' in error_msg or
        'session not found' in error_msg or
        'session-not-found' in error_msg
    )


async def call_tool_with_reconnect(
    host: str,
    port: int,
    tool_name: str,
    arguments: dict,
    transport: str = 'sse',
    max_attempts: int = 3
) -> CallToolResult:
    """Call an MCP tool with automatic reconnection on session termination.
    
    This function implements the MCP spec recommendation for handling 404/session-terminated
    errors by creating a fresh session and retrying the operation.
    
    According to the MCP specification, when a server terminates a session, it responds
    with HTTP 404 for requests that continue to use that session ID. The client should
    then initialize a new session (re-initialize without session ID).
    
    The Python MCP SDK does not automatically re-initialize sessions (there's an open
    issue for this), so this function implements the recommended pattern:
    1. Detect session termination error
    2. Create a FRESH session (never reuse dead sessions)
    3. Retry the operation
    
    Args:
        host: The hostname or IP address of the MCP server.
        port: The port number of the MCP server.
        tool_name: Name of the tool to call.
        arguments: Arguments to pass to the tool.
        transport: The communication transport ('sse' or 'streamable-http').
        max_attempts: Maximum number of retry attempts (default: 3).
        
    Returns:
        The result of the tool call.
        
    Raises:
        Exception: If all retry attempts fail or a non-retryable error occurs.
        
    Example:
        >>> ctx = with_agent_context(agent_id="agent://example", ...)
        >>> result = await call_tool_with_reconnect(
        ...     host="localhost",
        ...     port=10100,
        ...     tool_name="bigquery_search",
        ...     arguments={"query": "SELECT * FROM table", "_request_context": ctx}
        ... )
    """
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            # CRITICAL: Create a FRESH session for each attempt
            # Never reuse a dead session - this is the key fix
            async with init_session(host, port, transport) as session:
                logger.debug(f"Attempt {attempt}/{max_attempts}: Calling tool '{tool_name}'")
                result = await session.call_tool(tool_name, arguments=arguments)
                logger.debug(f"Tool '{tool_name}' completed successfully")
                return result
                
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # Check if this is a session termination error
            if _is_session_terminated_error(e):
                logger.warning(
                    f"[{attempt}/{max_attempts}] Session terminated for tool '{tool_name}'. "
                    f"Creating new session and retrying... Error: {error_msg}"
                )
                # Continue to next attempt with a fresh session
                if attempt < max_attempts:
                    # Small delay before retry to avoid overwhelming the server
                    # Exponential backoff: 0.5s, 1s, 1.5s
                    await asyncio.sleep(0.5 * attempt)
                    continue
                else:
                    # All attempts exhausted
                    logger.error(
                        f"Failed to call tool '{tool_name}' after {max_attempts} attempts. "
                        f"Last error: {last_error}"
                    )
                    raise
            else:
                # Non-retryable error, raise immediately
                logger.error(f"Non-retryable error calling tool '{tool_name}': {error_msg}")
                raise
    
    # Should not reach here, but just in case
    logger.error(
        f"Failed to call tool '{tool_name}' after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )
    raise last_error


@asynccontextmanager
async def init_session(host, port, transport='sse'):
    """Initializes and manages an MCP ClientSession based on the specified transport.

    This asynchronous context manager establishes a connection to an MCP server
    using either Server-Sent Events (SSE) or Streamable HTTP transport.
    It handles the setup and teardown of the connection and yields an active
    `ClientSession` object ready for communication.

    Args:
        host: The hostname or IP address of the MCP server.
        port: The port number of the MCP server.
        transport: The communication transport to use ('sse' or 'streamable-http').
                  Defaults to 'sse'.

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If an unsupported transport type is provided.
        Exception: Other potential exceptions during client initialization or
                   session setup.
    """

    if transport not in ['sse', 'streamable-http']:
        logger.error(f'Unsupported Transport type {transport}')
        raise ValueError(
            f"Unsupported transport type: {transport}. Must be 'sse' or 'streamable-http'"
        )
    
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        logger.info(f'Connecting to MCP server via SSE at {url}')
        
        # MCP spec requires Accept header with both application/json and text/event-stream
        headers = {
            'Accept': 'application/json, text/event-stream'
        }
        
        try:
            async with sse_client(url, headers=headers) as (read_stream, write_stream):
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
    
    elif transport == 'streamable-http':
        url = f'http://{host}:{port}/mcp'
        logger.info(f'Connecting to MCP server via Streamable HTTP at {url}')
        
        session = None
        read_stream = None
        write_stream = None
        
        try:
            # streamablehttp_client returns 3 elements: (read_stream, write_stream, connection_metadata)
            # The third element contains connection metadata and is typically ignored
            async with streamablehttp_client(url) as (read_stream, write_stream, _):
                logger.info('Streamable HTTP connection established')
                try:
                    async with ClientSession(
                        read_stream=read_stream,
                        write_stream=write_stream,
                    ) as session:
                        logger.info('Streamable HTTP Client Session Initializing...')
                        await session.initialize()
                        logger.info('Streamable HTTP Client Session Initialized Successfully')
                        yield session
                except Exception as e:
                    logger.error(f'Error initializing ClientSession: {e}', exc_info=True)
                    raise
                finally:
                    # Ensure proper cleanup of session
                    if session:
                        try:
                            logger.debug('Cleaning up Streamable HTTP session')
                        except Exception as cleanup_error:
                            logger.warning(f'Error during session cleanup: {cleanup_error}')
        except Exception as e:
            logger.error(f'Error connecting to Streamable HTTP server at {url}: {e}', exc_info=True)
            raise
        finally:
            # Ensure streams are properly closed
            logger.debug('Streamable HTTP connection cleanup complete')

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
