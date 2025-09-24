"""
Pytest configuration for ABI testing suite

This file contains shared fixtures and configuration for all ABI tests.
"""

import pytest
import asyncio
import logging
import sys
from pathlib import Path

# Add the abi-core directory to Python path for imports
abi_core_path = Path(__file__).parent.parent
sys.path.insert(0, str(abi_core_path))

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_config():
    """Provide test configuration settings."""
    return {
        "test_mode": True,
        "log_level": "INFO",
        "timeout": 30,
        "mock_external_services": True
    }

@pytest.fixture
async def mock_opa_server():
    """Mock OPA server for testing."""
    # This would be implemented based on testing needs
    pass

@pytest.fixture
async def mock_mcp_server():
    """Mock MCP server for testing."""
    # This would be implemented based on testing needs
    pass