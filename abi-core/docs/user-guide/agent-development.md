# Agent Development Guide

## Overview

This guide covers building custom AI agents in ABI-Core, from basic implementations to advanced patterns with tools, memory, and inter-agent communication.

## Agent Architecture

ABI-Core provides two base classes for agents:

1. **`BaseAgent`** - Simple agent with lifecycle management
2. **`AbiAgent`** - Enhanced agent with semantic enrichment and policy evaluation

## Creating Your First Agent

### Step 1: Generate Agent Scaffold

```bash
# In your ABI project
abi-core add agent my_agent \
  --description "My custom agent" \
  --model qwen2.5:3b
```

This creates:
```
agents/my_agent/
├── __init__.py
├── agent_my_agent.py    # Your agent implementation
├── main.py              # Entry point
├── models.py            # Data models
├── Dockerfile
└── requirements.txt
```

### Step 2: Implement Agent Logic

**File:** `agents/my_agent/agent_my_agent.py`

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class MyAgent(AbiAgent):
    """Custom agent implementation"""
    
    def __init__(self):
        super().__init__(
            agent_name='my_agent',
            description='My custom agent',
            content_types=['text/plain']
        )
        # Initialize your agent here
        self.setup_llm()
    
    def setup_llm(self):
        """Setup LLM with Ollama"""
        from langchain_ollama import ChatOllama
        import os
        
        model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        self.llm = ChatOllama(
            model=model,
            base_url=ollama_host,
            temperature=0.1
        )
    
    def process(self, enriched_input):
        """Process enriched input and return result"""
        query = enriched_input['query']
        
        abi_logging(f"Processing query: {query}")
        
        # Use LLM to process query
        response = self.llm.invoke(query)
        
        return {
            'result': response.content,
            'query': query
        }
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Stream responses for A2A protocol"""
        
        # Process with semantic enrichment and policy check
        result = self.handle_input(query)
        
        # Yield response in A2A format
        yield {
            'content': result['result'],
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

### Step 3: Test Your Agent

```bash
# Start services
docker-compose up -d

# Test agent
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, how can you help me?",
    "context_id": "test-001",
    "task_id": "task-001"
  }'
```

## Agent with Tools

### Adding LangChain Tools

```python
from abi_core.agent.agent import AbiAgent
from langchain.tools import tool
from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
import os

# Define custom tools
@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression"""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
    # In real implementation, call weather API
    return f"Weather in {city}: Sunny, 72°F"

class ToolAgent(AbiAgent):
    """Agent with tool calling capabilities"""
    
    def __init__(self):
        super().__init__(
            agent_name='tool_agent',
            description='Agent with tool calling',
            content_types=['text/plain']
        )
        self.setup_agent_with_tools()
    
    def setup_agent_with_tools(self):
        """Setup agent with tools"""
        
        # Initialize LLM
        model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        llm = ChatOllama(
            model=model,
            base_url=ollama_host,
            temperature=0.1
        )
        
        # Define tools
        tools = [calculate, get_weather]
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant with access to tools."),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        # Create agent
        agent = create_tool_calling_agent(llm, tools, prompt)
        
        # Create executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True
        )
    
    def process(self, enriched_input):
        """Process with tool calling"""
        query = enriched_input['query']
        
        # Execute with tools
        result = self.agent_executor.invoke({"input": query})
        
        return {
            'result': result['output'],
            'query': query
        }
```

**Usage:**
```python
agent = ToolAgent()
result = agent.handle_input("What is 25 * 4?")
print(result)  # Uses calculate tool

result = agent.handle_input("What's the weather in New York?")
print(result)  # Uses get_weather tool
```

## Agent with Memory

### Conversation Memory

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

## Agent-to-Agent Communication

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

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
import os

class StreamingAgent(AbiAgent):
    """Agent with streaming responses"""
    
    def __init__(self):
        super().__init__(
            agent_name='streaming_agent',
            description='Streams responses',
            content_types=['text/plain']
        )
        self.setup_llm()
    
    def setup_llm(self):
        model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        self.llm = ChatOllama(
            model=model,
            base_url=ollama_host,
            temperature=0.7,
            streaming=True
        )
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Stream response token by token"""
        
        accumulated = ""
        
        # Stream from LLM
        async for chunk in self.llm.astream(query):
            accumulated += chunk.content
            
            # Yield each chunk
            yield {
                'content': chunk.content,
                'response_type': 'text',
                'is_task_completed': False,
                'require_user_input': False
            }
        
        # Final message
        yield {
            'content': "",
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

### Error Handling

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class RobustAgent(AbiAgent):
    """Agent with robust error handling"""
    
    def process(self, enriched_input):
        """Process with error handling"""
        try:
            query = enriched_input['query']
            
            # Validate input
            if not query or len(query) < 3:
                raise ValueError("Query too short")
            
            # Process
            result = self.llm.invoke(query)
            
            return {
                'result': result.content,
                'status': 'success'
            }
            
        except ValueError as e:
            abi_logging(f"Validation error: {e}")
            return {
                'error': str(e),
                'status': 'validation_error'
            }
        
        except Exception as e:
            abi_logging(f"Processing error: {e}")
            return {
                'error': 'Internal processing error',
                'status': 'error'
            }
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Stream with error handling"""
        try:
            result = self.handle_input(query)
            
            if result.get('status') == 'error':
                yield {
                    'content': f"Error: {result['error']}",
                    'response_type': 'error',
                    'is_task_completed': True,
                    'require_user_input': False
                }
            else:
                yield {
                    'content': result['result'],
                    'response_type': 'text',
                    'is_task_completed': True,
                    'require_user_input': False
                }
        
        except Exception as e:
            abi_logging(f"Stream error: {e}")
            yield {
                'content': f"Fatal error: {str(e)}",
                'response_type': 'error',
                'is_task_completed': True,
                'require_user_input': False
            }
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

### 1. Use Semantic Enrichment

```python
# ✅ Good - Uses AbiAgent with enrichment
class MyAgent(AbiAgent):
    def process(self, enriched_input):
        # enriched_input has semantic context
        pass

# ❌ Bad - Bypasses enrichment
class MyAgent(BaseAgent):
    def process(self, raw_input):
        # Missing semantic context
        pass
```

### 2. Handle Errors Gracefully

```python
# ✅ Good
try:
    result = self.llm.invoke(query)
except Exception as e:
    abi_logging(f"Error: {e}")
    return {'error': 'Processing failed'}

# ❌ Bad
result = self.llm.invoke(query)  # Can crash
```

### 3. Log Important Events

```python
# ✅ Good
from abi_core.common.utils import abi_logging

abi_logging(f"Processing query: {query}")
abi_logging(f"Result: {result}")

# ❌ Bad
print(f"Processing: {query}")  # Won't appear in logs
```

### 4. Use Environment Variables

```python
# ✅ Good
model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

# ❌ Bad
model = 'qwen2.5:3b'  # Hardcoded
ollama_host = 'http://localhost:11434'  # Hardcoded
```

### 5. Implement Proper Streaming

```python
# ✅ Good
async def stream(self, query, context_id, task_id):
    # Process
    result = self.process_query(query)
    
    # Yield result
    yield {
        'content': result,
        'is_task_completed': True,
        'require_user_input': False
    }

# ❌ Bad
async def stream(self, query, context_id, task_id):
    return self.process_query(query)  # Not streaming
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
