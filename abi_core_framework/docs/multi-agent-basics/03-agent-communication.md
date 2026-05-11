# Agent Communication (A2A)

Agents talk to each other using the A2A protocol — JSON-RPC over HTTP with streaming support.

## The function

```python
from abi_core.common.abi_a2a import agent_connection
```

`agent_connection()` takes a source card, a target card, and a payload. It validates access (HMAC + OPA), then streams the response back.

## Calling another agent

```python
import json
from abi_core.common.abi_a2a import agent_connection
from config import AGENT_CARD  # Your agent's card

async def ask_another_agent(target_card, message):
    """Send a message to another agent and collect the response."""
    payload = {
        "message": {
            "messageId": "msg-001",
            "role": "user",
            "parts": [{"text": json.dumps({"text": message})}],
        }
    }

    response_text = ""
    async for chunk in agent_connection(AGENT_CARD, target_card, payload):
        # Extract text from A2A streaming response
        if hasattr(chunk, 'root') and hasattr(chunk.root, 'result'):
            result = chunk.root.result
            if hasattr(result, 'status') and hasattr(result.status, 'message'):
                for part in result.status.message.parts:
                    if hasattr(part, 'text'):
                        response_text = part.text

    return response_text
```

## The full flow

```
Agent A                          Agent B
   │                                │
   ├─ agent_connection(my_card, target_card, payload)
   │     │                          │
   │     ├─ Validate HMAC auth ─────┤
   │     ├─ Check OPA policies ─────┤
   │     ├─ HTTP POST (JSON-RPC) ───→ B.stream(query)
   │     │                          │   ├─ execute steps
   │     │                          │   ├─ call LLM
   │     ←─── streaming chunks ────←┤   └─ yield responses
   │                                │
   └─ process response              │
```

## Discover then call

The typical pattern: find an agent via Semantic Layer, then call it via A2A.

```python
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.common.abi_a2a import agent_connection

# 1. Find the right agent
target = await tool_find_agent.ainvoke("analyze financial data")

if target:
    # 2. Call it
    response = await ask_another_agent(target, "Analyze Q4 revenue trends")
```

## Security

Every A2A call is validated before execution:

1. **HMAC signature** — The source agent signs the request with its `shared_secret`
2. **OPA policy check** — Guardian evaluates if this agent-to-agent call is allowed
3. **Audit log** — The call is logged for compliance

If validation fails, `agent_connection()` raises `PermissionError`.

## What the target agent sees

The target agent receives the message through its normal `stream()` method — it doesn't know or care that the caller is another agent vs a user. The payload arrives as a query string (JSON), gets routed to a task, and executes steps.

## Next step

👉 [Your First Multi-Agent System](04-first-multi-agent-system.md)
