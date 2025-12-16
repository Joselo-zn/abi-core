import logging
import os 
import sys
import json

from typing import Any
from abi_core.common.types import ServerConfig

# ABI Logging Configuration
_abi_logger = None

def _setup_abi_logger():
    """Setup ABI logger with environment variable configuration."""
    global _abi_logger
    
    if _abi_logger is not None:
        return _abi_logger
    
    # Check if debug logging is enabled via environment variable
    debug_enabled = os.getenv('ABI_SETTINGS_LOGGING_DEBUG', 'False').lower() in ('true', '1', 'yes', 'on')
    
    # Create logger
    _abi_logger = logging.getLogger('abi_logger')
    _abi_logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    
    # Clear any existing handlers to avoid duplicates
    _abi_logger.handlers.clear()
    
    # Create handler that writes to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - ABI - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    _abi_logger.addHandler(handler)
    
    # Prevent propagation to avoid duplicate logs
    _abi_logger.propagate = False
    
    return _abi_logger

def abi_logging(message: str, level: str = 'info'):
    """
    ABI centralized logging function.
    
    Args:
        message (str): The message to log
        level (str): Log level ('debug', 'info', 'warning', 'error', 'critical')
    
    Usage:
        from common.utils import abi_logging
        abi_logging("My debug message")
        abi_logging("Error occurred", "error")
    """
    logger = _setup_abi_logger()
    
    level = level.lower()
    if level == 'debug':
        logger.debug(message)
    elif level == 'info':
        logger.info(message)
    elif level == 'warning':
        logger.warning(message)
    elif level == 'error':
        logger.error(message)
    elif level == 'critical':
        logger.critical(message)
    else:
        logger.info(message)  # Default to info if invalid level

# Legacy logger for backward compatibility
logger = logging.getLogger(__name__)

import re

# Parse SEMANTIC_LAYER_HOST which may contain protocol and port
SEMANTIC_LAYER_URL = os.getenv('SEMANTIC_LAYER_HOST', 'http://abi-semantic-layer:10100/sse')
TRANSPORT = os.getenv('TRANSPORT', 'sse')

# Extract host and port from URL if provided with protocol
# Supports formats: http://host:port/path or just host
url_match = re.match(r'https?://([^:/]+)(?::(\d+))?', SEMANTIC_LAYER_URL)
if url_match:
    HOST = url_match.group(1)
    PORT = int(url_match.group(2)) if url_match.group(2) else 10100
    URL = SEMANTIC_LAYER_URL
else:
    # Fallback: treat as plain hostname
    HOST = SEMANTIC_LAYER_URL.split(':')[0]
    PORT = int(os.getenv('SEMANTIC_LAYER_PORT', 10100))
    URL = f'http://{HOST}:{PORT}/sse'

def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration.
    
    Parses SEMANTIC_LAYER_HOST environment variable which can be:
    - Full URL: http://hostname:port/sse
    - Hostname only: hostname (uses SEMANTIC_LAYER_PORT or default 10100)
    
    Returns:
        ServerConfig with parsed host, port, transport, and url
    """
    abi_logging(f'[*] MCP Config: Host={HOST}, Port={PORT}, Transport={TRANSPORT}')
    return ServerConfig(
        host=HOST,
        port=PORT,
        transport=TRANSPORT,
        url=URL,
    )

def truncate(obj: Any, max_chars: int = 4000) -> str:
    """Convierte a JSON y recorta para no exceder num_ctx."""
    text = json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= max_chars else text[:max_chars] + "…"
