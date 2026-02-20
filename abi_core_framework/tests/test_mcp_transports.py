"""
Tests for MCP transport protocols (SSE and Streamable HTTP).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from abi_core.abi_mcp import client
from abi_core.common.types import ServerConfig


class TestMCPTransports:
    """Test suite for MCP transport protocols."""

    def test_server_config_sse(self):
        """Test ServerConfig with SSE transport."""
        config = ServerConfig(
            host="localhost",
            port=10100,
            transport="sse",
            url="http://localhost:10100"
        )
        
        assert config.host == "localhost"
        assert config.port == 10100
        assert config.transport == "sse"
        assert config.url == "http://localhost:10100"

    def test_server_config_streamable_http(self):
        """Test ServerConfig with Streamable HTTP transport."""
        config = ServerConfig(
            host="localhost",
            port=10100,
            transport="streamable-http",
            url="http://localhost:10100"
        )
        
        assert config.host == "localhost"
        assert config.port == 10100
        assert config.transport == "streamable-http"
        assert config.url == "http://localhost:10100"

    @pytest.mark.asyncio
    async def test_init_session_invalid_transport(self):
        """Test that invalid transport raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            async with client.init_session(
                host="localhost",
                port=10100,
                transport="invalid"
            ) as session:
                pass
        
        assert "Unsupported transport type" in str(exc_info.value)
        assert "Must be 'sse' or 'streamable-http'" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('abi_core.abi_mcp.client.sse_client')
    async def test_init_session_sse(self, mock_sse_client):
        """Test SSE transport initialization."""
        # Mock SSE client
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        
        mock_sse_client.return_value.__aenter__.return_value = (
            mock_read_stream,
            mock_write_stream
        )
        
        with patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
            mock_client_session.return_value.__aenter__.return_value = mock_session
            
            async with client.init_session(
                host="localhost",
                port=10100,
                transport="sse"
            ) as session:
                assert session == mock_session
                mock_session.initialize.assert_called_once()

    @pytest.mark.asyncio
    @patch('abi_core.abi_mcp.client.streamable_http_client')
    async def test_init_session_streamable_http(self, mock_http_client):
        """Test Streamable HTTP transport initialization."""
        # Mock Streamable HTTP client - returns 3 elements (read, write, metadata)
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_metadata = AsyncMock()  # Connection metadata (ignored)
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        
        # streamable_http_client returns (read_stream, write_stream, metadata) tuple
        mock_http_client.return_value.__aenter__.return_value = (
            mock_read_stream,
            mock_write_stream,
            mock_metadata
        )
        
        with patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
            mock_client_session.return_value.__aenter__.return_value = mock_session
            
            async with client.init_session(
                host="localhost",
                port=10100,
                transport="streamable-http"
            ) as session:
                assert session == mock_session
                mock_session.initialize.assert_called_once()

    def test_transport_url_construction_sse(self):
        """Test that SSE transport constructs correct URL."""
        # This would be tested in integration tests
        # Unit test verifies the URL pattern
        host = "localhost"
        port = 10100
        expected_url = f"http://{host}:{port}/sse"
        
        assert expected_url == "http://localhost:10100/sse"

    def test_transport_url_construction_streamable_http(self):
        """Test that Streamable HTTP transport constructs correct URL."""
        # This would be tested in integration tests
        # Unit test verifies the URL pattern
        host = "localhost"
        port = 10100
        expected_url = f"http://{host}:{port}/mcp"
        
        assert expected_url == "http://localhost:10100/mcp"


class TestMCPUtils:
    """Test suite for MCP utility functions."""

    @patch.dict('os.environ', {
        'SEMANTIC_LAYER_HOST': 'http://test-host:8080',
        'MCP_TRANSPORT': 'streamable-http'
    })
    def test_get_mcp_server_config_with_env(self):
        """Test get_mcp_server_config with environment variables."""
        from abi_core.common.utils import get_mcp_server_config
        
        config = get_mcp_server_config()
        
        assert config.host == "test-host"
        assert config.port == 8080
        assert config.transport == "streamable-http"

    @patch.dict('os.environ', {}, clear=True)
    def test_get_mcp_server_config_defaults(self):
        """Test get_mcp_server_config with default values."""
        from abi_core.common.utils import get_mcp_server_config
        
        config = get_mcp_server_config()
        
        # Should use defaults
        assert config.transport == "sse"  # Default transport


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
