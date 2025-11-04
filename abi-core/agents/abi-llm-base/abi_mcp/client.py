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
        ValueError: If an unsupported transport type is provided (implicitly,
                    as it won't match 'sse').
        Exception: Other potential exceptions during client initialization or
                   session setup.
    """

    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                logger.debug('SSE Client Session Initializing...')
                await session.initialize()
                logger.debug('SSE Cliente Session Initialized Successfully')
                yield session
    else:
        logger.error(f'Unsupported Transport type {transport}')
        raise ValueError(
            f"Unsupported transport type: {transport}. Must be 'sse'"
        )

async def find_agent(session: ClientSession, query) -> CallToolResult:
    """Call the tool 'find_agent' tool on the connected MCP server.

    Args:
        session: The active ClienteSession.
        query: The natural language query to send to the 'find_agent' tool.

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'find_agent' tool with query: '{query[:50]}...'")
    return await session.call_tool(
        name='find_agent',
        arguments={
            'query': query,
        },
    )

async def find_resource(session: ClientSession, resource) -> ReadResourceResult:
    """Reads a resource from the connected MCP server.

    Args:
        session: The active ClientSession.
        resource: The URI of the resource to read (e.g., 'resource://agent_cards/list').

    Returns:
        The result of the resource read operation.
    """
    logger.info(f'Reading resource: {resource}')
    return await session.read_resource(resource)

# TODO: Implementation of the other actions and tools
