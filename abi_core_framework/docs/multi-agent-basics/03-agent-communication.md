# Agent Communication (A2A)

Agents talk to each other using a standard messaging protocol called A2A. One function call, streaming responses.

## The function

```python
from abi_core.common.abi_a2a import agent_connection
```

`agent_connection()` takes your agent's card, the target agent's card, and a message. It checks security, sends the message, and streams the response back.

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

The typical pattern: find an agent, then talk to it.

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

Every agent-to-agent call is checked before it goes through:

1. **Signature check** — The message is signed to prove who sent it
2. **Rules check** — Guardian checks if this communication is allowed
3. **Logged** — Every call is recorded for auditing

If the check fails, `agent_connection()` raises an error and the call doesn't happen.

## What the target agent sees

The target agent receives the message through its normal `stream()` method — it doesn't know or care if the caller is another agent or a human user. The message arrives, gets routed to a task, and runs normally.

## Next step

👉 [Your First Multi-Agent System](04-first-multi-agent-system.md)
