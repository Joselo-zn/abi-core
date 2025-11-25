# Agent Communication (A2A)

Learn how agents communicate with each other using the A2A protocol.

## A2A Protocol

**A2A** (Agent-to-Agent) is the protocol that allows agents to:
- Send messages to each other
- Request tasks
- Share results

## Basic Communication

### Agent A calls Agent B

```python
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
import httpx
import json
from uuid import uuid4

async def call_agent(agent_card, message):
    """Call another agent"""
    async with httpx.AsyncClient() as http_client:
        a2a_client = A2AClient(http_client, agent_card)
        
        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{'kind': 'text', 'text': message}],
                    'messageId': str(uuid4()),
                    'contextId': str(uuid4())
                }
            )
        )
        
        async for response in a2a_client.send_message_stream(request):
            if hasattr(response.root.result, 'artifact'):
                return response.root.result.artifact
```

## Complete Example

### Coordinator Agent

```python
from abi_core.agent.agent import AbiAgent
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

class CoordinatorAgent(AbiAgent):
    async def process_complex_task(self, task):
        """Coordinate multiple agents"""
        
        # 1. Find analyst agent
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            result = await client.find_agent(
                session,
                "agent that analyzes data"
            )
            analyst_card = AgentCard(**json.loads(result.content[0].text))
        
        # 2. Call analyst
        analysis = await call_agent(
            analyst_card,
            f"Analyze: {task}"
        )
        
        # 3. Find reporter agent
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            result = await client.find_agent(
                session,
                "agent that generates reports"
            )
            reporter_card = AgentCard(**json.loads(result.content[0].text))
        
        # 4. Call reporter
        report = await call_agent(
            reporter_card,
            f"Generate report from: {analysis}"
        )
        
        return report
```

## Communication Flow

```
User
  ↓
Coordinator
  ├─→ Analyst → Result 1
  └─→ Reporter → Result 2
  ↓
Final Result
```

## Next Steps

- [Your first multi-agent system](04-first-multi-agent-system.md)
- [Semantic layer](../semantic-layer/01-what-is-semantic-layer.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
