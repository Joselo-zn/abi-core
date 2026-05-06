# Agent Development Guide

## Overview

This guide covers building custom AI agents in ABI-Core, from basic implementations to advanced patterns with tools, memory, and inter-agent communication.

## Agent Architecture

ABI-Core provides:

- **`AbiAgent`** — Base class with LLM creation, streaming with heartbeat, and tool graph support
- **`AbiCore`** — Application runner with decorator-based task/tool registration
- **`AgentResponse`** — Typed response objects (success, error, status, input_required, empty)
- **`ToolExecutionGraph`** — Deterministic DAG for strict tool execution order

## Creating Your First Agent

### Step 1: Generate Agent Scaffold

```bash
abi-core add agent my_agent \
  --description "My custom agent" \
  --model qwen2.5:3b
```

This creates:
```
agents/my_agent/
├── config/
│   ├── __init__.py
│   └── config.py          # Centralized config (LLM_CONFIG, ports, etc.)
├── agent_my_agent.py       # Your agent implementation
├── main.py                 # Entry point (AbiCore runner)
├── agent_cards/            # Agent card (auto-created)
├── models.py
├── Dockerfile
└── requirements.txt
```

### Step 2: Understand the Code

**`main.py`** — Ultra-minimal entry point:

```python
from agent_my_agent import MyAgentAgent
from abi_core.agent import AbiCore

agent = AbiCore()
agent.run(MyAgentAgent())
```

`AbiCore()` auto-imports `config` and `AGENT_CARD` from the local `config/` package. `agent.run()` starts the A2A server.

**`agent_my_agent.py`** — Agent class:

```python
from abi_core.agent import AbiAgent
from abi_core.common import prompts
from config import config


class MyAgentAgent(AbiAgent):
    """My custom agent"""

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[],  # Add your LangChain tools here
            system_prompt=prompts.WORKER_PROMPT,
        )

    # stream() is inherited from AbiAgent with heartbeat support.
    # Override only if you need custom behaviour:
    #
    # async def stream(self, query, context_id, task_id):
    #     yield AgentResponse.success("custom response", agent=self.agent_name)
```

### Step 3: Test Your Agent

```bash
docker-compose up -d
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello!", "context_id": "test-001", "task_id": "task-001"}'
```

## Decorator-Based Tasks & Tools

Register deterministic tasks and tools directly on the `AbiCore` instance in `main.py`:

### Tasks (Deterministic DAG)

Tasks run in strict topological order — the LLM never decides when to call them:

```python
from my_agent import MyAgent
from abi_core.agent import AbiCore

agent = AbiCore()

@agent.step(name="fetch_data")
def fetch_data(query):
    return {"rows": db.execute(query)}

@agent.step(
    name="clean_data",
    depends_on=["fetch_data"],
    input_map={"raw": "$fetch_data.rows"},
)
def clean_data(raw):
    return {"cleaned": [r for r in raw if r["valid"]]}

agent.run(MyAgent())
```

### Tools (DAG + LLM-invocable)

Tools are DAG nodes that are also exposed as LangChain tools for the LLM:

```python
@agent.tool(name="calculate")
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    return str(eval(expression))
```

### MCP Remote Tools

Call remote MCP tools via `MCPToolkit` with HMAC authentication — no local function needed:

```python
@agent.mcp_tool(
    name="bigquery_search",
    input_map={"query": "$input.user_query"},
)
```

Or with a wrapper for pre/post processing:

```python
@agent.mcp_tool(name="bigquery_search")
async def bigquery_search(query):
    return {"query": sanitize(query)}
```

### How it works

1. Decorators register functions before `agent.run()` is called
2. `run()` builds a `ToolExecutionGraph` (LangGraph DAG) from all registered nodes
3. The DAG is injected into the agent as `self.tool_graph`
4. `@agent.tool()` functions are also converted to LangChain `StructuredTool` and injected as `self.extra_tools`
5. `@agent.mcp_tool()` nodes are resolved via `MCPToolkit` with HMAC auth from the agent card

## Agent with LangChain Tools (Classic)

You can also pass tools directly to `AbiAgent` in the constructor:

```python
from langchain.tools import tool

@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression"""
    return str(eval(expression))

@tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
    return f"Weather in {city}: Sunny, 72°F"

class ToolAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[calculate, get_weather],
            system_prompt="You are a helpful assistant with access to tools.",
        )
```

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
import os

class MemoryAgent(AbiAgent):
    """Agent with conversation memory"""
    
    def __init__(self):
        super().__init__(
            agent_name='memory_agent',
            description='Agent with memory',
            content_types=['text/plain']
        )
        self.conversations = {}  # Store conversations by context_id
        self.setup_llm()
    
    def setup_llm(self):
        """Setup LLM"""
        model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        self.llm = ChatOllama(
            model=model,
            base_url=ollama_host,
            temperature=0.7
        )
    
    def get_conversation(self, context_id: str):
        """Get or create conversation for context"""
        if context_id not in self.conversations:
            memory = ConversationBufferMemory()
            self.conversations[context_id] = ConversationChain(
                llm=self.llm,
                memory=memory,
                verbose=True
            )
        return self.conversations[context_id]
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Stream with memory"""
        
        # Get conversation for this context
        conversation = self.get_conversation(context_id)
        
        # Process with memory
        response = conversation.predict(input=query)
        
        yield {
            'content': response,
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

**Usage:**
```bash
# First message
curl -X POST http://localhost:8000/stream \
  -d '{"query": "My name is Alice", "context_id": "conv-001", "task_id": "t1"}'
# Response: "Nice to meet you, Alice!"

# Second message (remembers name)
curl -X POST http://localhost:8000/stream \
  -d '{"query": "What is my name?", "context_id": "conv-001", "task_id": "t2"}'
# Response: "Your name is Alice."
```

## Agent with Memory

### Conversation Memory

### Calling Another Agent

```python
from abi_core.agent.agent import AbiAgent
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
from uuid import uuid4
import httpx
import json

class OrchestratorAgent(AbiAgent):
    """Agent that orchestrates other agents"""
    
    def __init__(self):
        super().__init__(
            agent_name='orchestrator',
            description='Orchestrates multiple agents',
            content_types=['text/plain']
        )
    
    async def find_and_call_agent(self, capability: str, query: str):
        """Find agent by capability and call it"""
        
        # Step 1: Find agent via semantic layer
        config = get_mcp_server_config()
        
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            result = await client.find_agent(session, capability)
            
            if not result.content:
                return {"error": "No agent found"}
            
            agent_card_data = json.loads(result.content[0].text)
            agent_card = AgentCard(**agent_card_data)
        
        # Step 2: Call the agent via A2A
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(http_client, agent_card)
            
            request = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        'role': 'user',
                        'parts': [{'kind': 'text', 'text': query}],
                        'messageId': str(uuid4()),
                        'contextId': str(uuid4())
                    }
                )
            )
            
            # Get response
            async for response in a2a_client.send_message_stream(request):
                if hasattr(response.root.result, 'artifact'):
                    return response.root.result.artifact
        
        return {"error": "No response from agent"}
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Orchestrate multiple agents"""
        
        # Example: "Analyze AAPL stock and execute a trade"
        
        # Step 1: Find analyst agent
        analysis = await self.find_and_call_agent(
            "agent that analyzes stocks",
            f"Analyze AAPL stock"
        )
        
        yield {
            'content': f"Analysis: {analysis}",
            'response_type': 'text',
            'is_task_completed': False,
            'require_user_input': False
        }
        
        # Step 2: Find trader agent
        trade_result = await self.find_and_call_agent(
            "agent that executes trades",
            f"Buy 100 shares of AAPL based on analysis: {analysis}"
        )
        
        yield {
            'content': f"Trade executed: {trade_result}",
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

## Advanced Patterns

### Streaming Responses

`AbiAgent` provides a default `stream()` with SSE heartbeat support. Override only when needed:

```python
from abi_core.agent import AbiAgent, AgentResponse

class StreamingAgent(AbiAgent):
    """Agent with custom streaming"""

    async def stream(self, query: str, context_id: str, task_id: str):
        """Custom stream with progress updates"""

        yield AgentResponse.status(
            "Analyzing query...",
            agent=self.agent_name,
            context_id=context_id,
            task_id=task_id,
        )

        # Your custom logic here
        result = await self.llm.ainvoke(query)

        yield AgentResponse.success(
            result.content,
            agent=self.agent_name,
            model=self.llm_config.get("model", "unknown"),
            context_id=context_id,
            task_id=task_id,
        )
```

### Error Handling

`AbiAgent.stream()` handles errors automatically. For custom error handling:

```python
from abi_core.agent import AbiAgent, AgentResponse

class RobustAgent(AbiAgent):
    async def stream(self, query: str, context_id: str, task_id: str):
        try:
            if len(query) < 3:
                yield AgentResponse.input_required(
                    "Please provide a more specific query.",
                    agent=self.agent_name,
                )
                return

            result = await self.llm.ainvoke(query)
            yield AgentResponse.success(result.content, agent=self.agent_name)

        except Exception as e:
            abi_logging(f"[❌] Error: {e}", level="error")
            yield AgentResponse.error(str(e), agent=self.agent_name)
```

## Testing Agents

### Unit Tests

```python
import pytest
from agents.my_agent.agent_my_agent import MyAgent

def test_agent_initialization():
    """Test agent initializes correctly"""
    agent = MyAgent()
    assert agent.agent_name == 'my_agent'
    assert agent.llm is not None

def test_agent_process():
    """Test agent processes input"""
    agent = MyAgent()
    result = agent.handle_input("Hello")
    assert 'result' in result
    assert result['result'] is not None

@pytest.mark.asyncio
async def test_agent_stream():
    """Test agent streaming"""
    agent = MyAgent()
    
    responses = []
    async for response in agent.stream("Test query", "ctx-001", "task-001"):
        responses.append(response)
    
    assert len(responses) > 0
    assert responses[-1]['is_task_completed'] == True
```

### Integration Tests

```python
import pytest
import httpx

@pytest.mark.asyncio
async def test_agent_http_endpoint():
    """Test agent via HTTP"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/stream",
            json={
                "query": "Test query",
                "context_id": "test-001",
                "task_id": "task-001"
            }
        )
        assert response.status_code == 200
```

## Best Practices

### 1. Use AbiCore Runner

```python
# ✅ Good — minimal main.py
from my_agent import MyAgent
from abi_core.agent import AbiCore

agent = AbiCore()
agent.run(MyAgent())

# ❌ Bad — manual boilerplate
from config import config, AGENT_CARD
from abi_core.agent.agent_factory import agent_factory
def main():
    return agent_factory(MyAgent(), config, AGENT_CARD)
```

### 2. Use AgentResponse

```python
# ✅ Good — typed responses
yield AgentResponse.success("Answer", agent=self.agent_name)
yield AgentResponse.error("Something broke", agent=self.agent_name)
yield AgentResponse.status("Working...", agent=self.agent_name)

# ❌ Bad — raw dicts
yield {"content": "Answer", "is_task_completed": True}
```

### 3. Use Centralized Config

```python
# ✅ Good — config from config/config.py
from config import config
llm = create_llm(config.LLM_CONFIG)

# ❌ Bad — hardcoded values
model = 'qwen2.5:3b'
ollama_host = 'http://localhost:11434'
```

### 4. Use abi_logging

```python
# ✅ Good
from abi_core.common.utils import abi_logging
abi_logging(f"Processing: {query}")

# ❌ Bad
print(f"Processing: {query}")
```

### 5. Use Decorators for Tools

```python
# ✅ Good — declarative, wired to DAG
@agent.step(name="clean", depends_on=["fetch"])
def clean(data): ...

@agent.mcp_tool(name="bigquery_search")

# ❌ Bad — manual tool graph construction
graph = ToolExecutionGraph()
graph.add_node(ToolGraphNode(id="clean", fn=clean, ...))
```

## Deployment

### Docker Configuration

The generated `Dockerfile` is production-ready:

```dockerfile
FROM abi-image:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### Environment Variables

Configure via `.abi/runtime.yaml`:

```yaml
agents:
  my_agent:
    model: "qwen2.5:3b"
    port: 8000
    ollama_host: "http://my-project-ollama:11434"
```

## Next Steps

- [Complete Example](complete-example.md) - See agents in action
- [Policy Development](policy-development.md) - Add security policies
- [Semantic Enrichment](semantic-enrichment.md) - Understand enrichment

## Resources

- [LangChain Documentation](https://python.langchain.com/)
- [A2A Protocol](../agent_protocols.md)
- [Ollama Models](https://ollama.ai/library)
