# abi_core/security/agent_auth.py
import json, time, base64, hmac, hashlib
from uuid import uuid4
from pathlib import Path
from datetime import datetime


def with_agent_context(agent_id: str, **additional_context):
    """
    Helper para inyectar contexto de agente en requests
    
    Usage:
        context = with_agent_context("planner", tool_name="find_agent")
        result = find_agent("search query", _request_context=context)
    """
    
    return {
        "agent_id": agent_id,
        "headers": {
            "X-Agent-ID": agent_id,
            "User-Agent": f"ABI-Agent/{agent_id}/1.0"
        },
        "timestamp": datetime.utcnow().isoformat(),
        **additional_context
    }

def load_agent_card(card_path: str) -> dict:
    try:
        card_path = Path(card_path).resolve()
    except Exception as e:
        raise ValueError(f"Invalid agent card path: {card_path}") from e    
    
    with open(card_path, "r") as f:
        return json.load(f)

def sign_payload_hmac(shared_secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(shared_secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def build_semantic_context_from_card(
    agent_card_path: str,
    tool_name: str,
    query: str,
    mcp_method: str = "callTool",
    user_email: str = None,
):
    """
    Build semantic context from agent card with optional user information.
    
    Args:
        agent_card_path: Path to agent card file
        tool_name: Name of the MCP tool being called
        query: Query string
        mcp_method: MCP method (default: "callTool")
        user_email: Optional email of the user initiating the request
    
    Returns:
        Context dictionary with agent and user information
    """
    card = load_agent_card(agent_card_path)
    agent_id = card["id"]
    
    shared_secret = card["auth"]["shared_secret"]

    payload = {
        "agent_id": agent_id,
        "tool": tool_name,
        "query": query,
        "ts": int(time.time()),
        "nonce": uuid4().hex,
    }
    
    # Add user email to payload if provided
    if user_email:
        payload["user_email"] = user_email

    signature = sign_payload_hmac(shared_secret, payload)

    headers = {
        "X-ABI-Agent-ID": agent_id,
        "X-ABI-Key-Id": card["auth"]["key_id"],
        "X-ABI-Signature": signature,
        "X-ABI-Timestamp": str(payload["ts"]),
        "X-ABI-Nonce": payload["nonce"],
    }
    
    # Add user email to headers if provided
    if user_email:
        headers["X-ABI-User-Email"] = user_email

    ctx = with_agent_context(
        agent_id=agent_id,
        tool_name=tool_name,
        mcp_method=mcp_method,
        headers=headers,
        payload=payload,
    )
    
    # Add user_email at top level for easy access
    if user_email:
        ctx["user_email"] = user_email
    
    return ctx
