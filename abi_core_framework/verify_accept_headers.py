#!/usr/bin/env python3
"""
Simple verification script for MCP Accept header compliance.
Runs without pytest dependency.
"""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


async def verify_sse_accept_header():
    """Verify SSE transport sends MCP-compliant Accept header."""
    print("Testing SSE Accept Header Compliance...")
    
    from abi_core.abi_mcp import client
    
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
        if call_args is None:
            print("  ✗ FAILED: sse_client was not called")
            return False
        
        # Check that headers were passed
        headers = call_args.kwargs.get('headers', {})
        
        # Verify MCP compliance
        if 'Accept' not in headers:
            print("  ✗ FAILED: Accept header not present")
            return False
        
        accept_value = headers['Accept']
        
        if 'application/json' not in accept_value:
            print(f"  ✗ FAILED: application/json not in Accept header: {accept_value}")
            return False
        
        if 'text/event-stream' not in accept_value:
            print(f"  ✗ FAILED: text/event-stream not in Accept header: {accept_value}")
            return False
        
        print(f"  ✓ PASSED: Accept header is MCP compliant: {accept_value}")
        return True


async def verify_streamable_http_accept_header():
    """Verify Streamable HTTP transport has MCP-compliant Accept header."""
    print("\nTesting Streamable HTTP Accept Header Compliance...")
    
    try:
        from mcp.client.streamable_http import StreamableHTTPTransport
        
        transport = StreamableHTTPTransport("http://localhost:10100/mcp")
        
        # Verify request_headers contains correct Accept header
        if 'accept' not in transport.request_headers:
            print("  ✗ FAILED: accept header not in request_headers")
            return False
        
        accept_value = transport.request_headers['accept']
        
        if 'application/json' not in accept_value:
            print(f"  ✗ FAILED: application/json not in Accept header: {accept_value}")
            return False
        
        if 'text/event-stream' not in accept_value:
            print(f"  ✗ FAILED: text/event-stream not in Accept header: {accept_value}")
            return False
        
        print(f"  ✓ PASSED: Accept header is MCP compliant: {accept_value}")
        return True
    
    except Exception as e:
        print(f"  ✗ FAILED: Exception occurred: {e}")
        return False


async def verify_both_transports():
    """Verify both transports use compatible Accept headers."""
    print("\nTesting Both Transports Have Compatible Accept Headers...")
    
    from abi_core.abi_mcp import client
    from mcp.client.streamable_http import StreamableHTTPTransport
    
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
    transport = StreamableHTTPTransport("http://localhost:10100/mcp")
    http_accept = transport.request_headers.get('accept', '')
    
    # Both should have the same content types
    sse_has_json = 'application/json' in sse_accept
    sse_has_sse = 'text/event-stream' in sse_accept
    http_has_json = 'application/json' in http_accept
    http_has_sse = 'text/event-stream' in http_accept
    
    all_passed = sse_has_json and sse_has_sse and http_has_json and http_has_sse
    
    print(f"  SSE Accept: {sse_accept}")
    print(f"  HTTP Accept: {http_accept}")
    
    if all_passed:
        print("  ✓ PASSED: Both transports are MCP compliant")
        return True
    else:
        print("  ✗ FAILED: One or both transports missing required content types")
        return False


async def main():
    """Run all verification tests."""
    print("=" * 70)
    print("MCP Accept Header Compliance Verification")
    print("=" * 70)
    
    results = []
    
    # Run tests
    results.append(await verify_sse_accept_header())
    results.append(await verify_streamable_http_accept_header())
    results.append(await verify_both_transports())
    
    # Summary
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
