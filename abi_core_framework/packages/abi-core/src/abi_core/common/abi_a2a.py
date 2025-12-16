from typing import AsyncIterable
from uuid import uuid4
import httpx
import inspect

from abi_core.common.utils import abi_logging
from abi_core.security.a2a_access_validator import get_validator
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
)


async def agent_connection(
    source_card: AgentCard,
    target_card: AgentCard,
    payload: dict[str, any]
) -> AsyncIterable[dict[str, any]]:
    """
    Establish validated A2A connection between agents
    
    Args:
        source_card: Source agent card (caller)
        target_card: Target agent card (callee)
        payload: Message payload
        
    Yields:
        Response chunks from target agent
        
    Raises:
        PermissionError: If A2A validation fails
    """
    # Extract message for logging
    message_text = ""
    if 'message' in payload and 'parts' in payload['message']:
        parts = payload['message']['parts']
        if parts and len(parts) > 0 and 'text' in parts[0]:
            message_text = parts[0]['text']
    
    # Validate A2A access
    validator = get_validator()
    is_allowed, reason = await validator.validate_a2a_access(
        source_agent_card=source_card,
        target_agent_card=target_card,
        message=message_text,
        additional_context={
            'task_id': payload.get('message', {}).get('messageId'),
            'context_id': payload.get('message', {}).get('contextId')
        }
    )
    
    if not is_allowed:
        error_msg = (
            f"A2A communication denied: {source_card.name} -> {target_card.name}. "
            f"Reason: {reason}"
        )
        abi_logging(f"❌ {error_msg}")
        raise PermissionError(error_msg)
    
    abi_logging(f"✅ A2A validated: {source_card.name} -> {target_card.name}")
    
    # Establish connection
    timeout_config = httpx.Timeout(timeout=180.0, read=180.0, write=30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
        abi_logging(f"Target URL: {target_card.url if hasattr(target_card, 'url') else 'No URL'}")
        
        client = A2AClient(httpx_client, target_card)
        
        request = SendStreamingMessageRequest(
            id=str(uuid4()), 
            params=MessageSendParams(**payload)
        )
        
        # Find appropriate method
        response_stream = None
        for method_name in ['send_message_stream', 'send_streaming_message', 'stream_message', 'send_message']:
            if hasattr(client, method_name):
                response_stream = getattr(client, method_name)(request)
                abi_logging(f"Using method: {method_name}")
                break
        
        if response_stream is None:
            available = [m for m in dir(client) if 'send' in m.lower() or 'stream' in m.lower()]
            abi_logging(f"❌ No suitable method found. Available: {available}")
            raise AttributeError("No suitable streaming method found in A2AClient")
        
        # Handle response
        if inspect.iscoroutine(response_stream):
            abi_logging("Awaiting coroutine response...")
            response = await response_stream
            if hasattr(response, 'root'):
                yield response
        elif hasattr(response_stream, '__aiter__'):
            abi_logging("Streaming async iterator...")
            async for chunk in response_stream:
                if isinstance(chunk.root, SendStreamingMessageSuccessResponse) and \
                   isinstance(chunk.root.result, TaskArtifactUpdateEvent):
                    yield chunk
        else:
            abi_logging(f"⚠️ Unexpected response type: {type(response_stream)}")
