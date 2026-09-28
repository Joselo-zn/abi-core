import asyncio
from typing import AsyncIterable
from uuid import uuid4
import httpx

from abi_core.common.utils import abi_logging
from abi_core.security.a2a_access_validator import get_validator
from a2a.client import Client, ClientFactory, ClientConfig
from a2a.types import (
    AgentCard,
)
from abi_core.common.agent_card_loader import get_agent_url


async def agent_connection(
    source_card: AgentCard,
    target_card: AgentCard,
    payload: dict[str, any],
    grace_period: float = 180.0,
) -> AsyncIterable[dict[str, any]]:
    """
    Establish validated A2A connection between agents

    Args:
        source_card: Source agent card (caller)
        target_card: Target agent card (callee)
        payload: Message payload
        grace_period: Max seconds to wait for the NEXT event (heartbeat or
            real data) before giving up — resets on every event seen, not a
            fixed budget for the whole call. See
            .abi/specs/not-implemented/generic-task-heartbeat-artifact.md.
            Was a hardcoded httpx.Timeout(read=180.0) before — same default
            value, now a real per-call parameter instead of a constant.

    Yields:
        Response chunks from target agent

    Raises:
        PermissionError: If A2A validation fails
        TimeoutError: If no event (heartbeat or real data) arrives from the
            target agent within `grace_period` — the target genuinely
            stopped responding, not just slow (a healthy target's own
            heartbeat, emitted every _HEARTBEAT_INTERVAL seconds by its
            stream(), keeps resetting this well before grace_period hits).
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
    
    # Establish connection. `read=None` — no fixed transport-level cutoff:
    # the InactivityWatchdog below now owns the "give up" decision, fed by
    # every event (heartbeat or real data) instead of a constant nothing
    # could reset. `write`/`connect` stay bounded — those are genuinely
    # short, fixed operations, not "wait for a long-running task."
    timeout_config = httpx.Timeout(timeout=None, read=None, write=30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
        target_url = get_agent_url(target_card)
        abi_logging(f"Target URL: {target_url or 'No URL'}")
        
        from a2a.types import Message as A2AMessage, Part
        
        # Build A2A Message from payload
        parts_data = payload.get("message", {}).get("parts", [])
        parts = []
        for p in parts_data:
            if p.get("kind") == "text":
                parts.append(Part(text=p.get("text", "")))
        
        # Map role string to protobuf enum
        from a2a.types import Role
        role_str = payload.get("message", {}).get("role", "user")
        role_enum = Role.ROLE_USER if role_str == "user" else Role.ROLE_AGENT

        message = A2AMessage(
            role=role_enum,
            parts=parts,
            message_id=payload.get("message", {}).get("messageId") or str(uuid4()),
            context_id=payload.get("message", {}).get("contextId") or str(uuid4()),
        )
        
        from a2a.utils import TransportProtocol
        client_config = ClientConfig(
            httpx_client=httpx_client,
            streaming=True,
            supported_protocol_bindings=[TransportProtocol.JSONRPC],
        )
        factory = ClientFactory(client_config)
        client = factory.create(target_card)
        
        abi_logging(f"Streaming via Client.send_message...")
        from a2a.types import SendMessageRequest, SendMessageConfiguration
        request = SendMessageRequest(
            message=message,
            configuration=SendMessageConfiguration(
                accepted_output_modes=["text/plain"],
            ),
        )
        from abi_core.agent.heartbeat import InactivityWatchdog

        connection_key = payload.get("message", {}).get("messageId") or str(uuid4())
        watchdog = InactivityWatchdog(grace_period=grace_period)
        watchdog.touch(connection_key)

        stream_iter = client.send_message(request).__aiter__()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        stream_iter.__anext__(), timeout=grace_period
                    )
                except StopAsyncIteration:
                    break
                watchdog.touch(connection_key)
                yield event
        except asyncio.TimeoutError:
            abi_logging(
                f"[⚠️] No activity from {target_card.name} for {grace_period}s "
                "(no heartbeat, no result) — giving up.",
                level="warning",
            )
            raise TimeoutError(
                f"{target_card.name} stopped responding — no event for {grace_period}s."
            )
        finally:
            watchdog.forget(connection_key)
