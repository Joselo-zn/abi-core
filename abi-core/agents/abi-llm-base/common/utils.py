import logging
import os 

from common.types import ServerConfig

logger = logging.getLogger(__name__)

URL = os.getenv('MCP_URL', 'http://mcp-server:10100/sse')
TRANSPORT = os.getenv('TRANSPORT', 'sse')
PORT = os.getenv('MCP_PORT', 10100)
HOST = os.getenv('MCP_HOST', '0.0.0.0')

def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration."""
    logger.info(f'[*] Getting server configuration')
    return ServerConfig(
        host=HOST,
        port=PORT,
        transport=TRANSPORT,
        url=URL,
    )
