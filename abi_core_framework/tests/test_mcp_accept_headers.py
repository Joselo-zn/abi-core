"""
Tests for MCP Accept header compliance.

Verifies that both SSE and Streamable HTTP transports send the correct
Accept header as required by the MCP specification:
"The client MUST include an Accept header, listing both application/json 
and text/event-stream as supported content types."
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from abi_core.abi_mcp import client


@pytest.mark.asyncio
async def test_sse_accept_header_compliance():
    """Verify SSE transport sends MCP-compliant Accept header."""
    
    # Mock the sse_client context manager
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    
    with patch('abi_core.abi_mcp.client.sse_client') as mock_sse, \
         patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
        
        # Setup mock returns
        mock_sse.return_value.__aenter__.return_value = (mock_read_stream, mock_write_stream)
        mock_client_session.return_value.__aenter__.return_value = mock_session
        
        # Call init_session with SSE transport
        async with client.init_session("localhost", 10100, "sse") as session:
            pass
        
        # Verify sse_client was called with correct headers
        call_args = mock_sse.call_args
        assert call_args is not None, "sse_client was not called"
        
        # Check that headers were passed
        headers = call_args.kwargs.get('headers', {})
        
        # Verify MCP compliance
        assert 'Accept' in headers, "Accept header not present"
        accept_value = headers['Accept']
        assert 'application/json' in accept_value, "application/json not in Accept header"
        assert 'text/event-stream' in accept_value, "text/event-stream not in Accept header"
        
        print(f"✓ SSE Accept header is MCP compliant: {accept_value}")


@pytest.mark.asyncio
async def test_streamable_http_accept_header_compliance():
    """Verify Streamable HTTP transport has MCP-compliant Accept header."""
    
    # Test the SDK's StreamableHTTPTransport class directly
    from mcp.client.streamable_http import StreamableHTTPTransport
    
    transport = StreamableHTTPTransport("http://localhost:10100/mcp")
    
    # Verify request_headers contains correct Accept header
    assert 'accept' in transport.request_headers, "accept header not in request_headers"
    
    accept_value = transport.request_headers['accept']
    assert 'application/json' in accept_value, "application/json not in Accept header"
    assert 'text/event-stream' in accept_value, "text/event-stream not in Accept header"
    
    print(f"✓ Streamable HTTP Accept header is MCP compliant: {accept_value}")


@pytest.mark.asyncio
async def test_both_transports_have_same_accept_header():
    """Verify both transports use the same Accept header value."""
    
    expected_accept = "application/json, text/event-stream"
    
    # Test SSE
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    
    with patch('abi_core.abi_mcp.client.sse_client') as mock_sse, \
         patch('abi_core.abi_mcp.client.ClientSession') as mock_client_session:
        
        mock_sse.return_value.__aenter__.return_value = (mock_read_stream, mock_write_stream)
        mock_client_session.return_value.__aenter__.return_value = mock_session
        
        async with client.init_session("localhost", 10100, "sse"):
            pass
        
        sse_headers = mock_sse.call_args.kwargs.get('headers', {})
        sse_accept = sse_headers.get('Accept', '')
    
    # Test Streamable HTTP
    from mcp.client.streamable_http import StreamableHTTPTransport
    transport = StreamableHTTPTransport("http://localhost:10100/mcp")
    http_accept = transport.request_headers.get('accept', '')
    
    # Both should have the same content types (order may vary)
    assert 'application/json' in sse_accept
    assert 'text/event-stream' in sse_accept
    assert 'application/json' in http_accept
    assert 'text/event-stream' in http_accept
    
    print(f"✓ SSE Accept: {sse_accept}")
    print(f"✓ HTTP Accept: {http_accept}")
    print("✓ Both transports are MCP compliant")


if __name__ == "__main__":
    # Run tests directly
    import asyncio
    
    print("Testing MCP Accept Header Compliance\n")
    print("=" * 60)
    
    asyncio.run(test_sse_accept_header_compliance())
    print()
    
    asyncio.run(test_streamable_http_accept_header_compliance())
    print()
    
    asyncio.run(test_both_transports_have_same_accept_header())
    print()
    
    print("=" * 60)
    print("✓ All Accept header compliance tests passed!")
