# Your First Agent

You've already created your first project. Now you'll learn to create and customize AI agents from scratch.

## What is an Agent?

An **agent** is a program that:
- Understands natural language
- Generates intelligent responses
- Can use tools
- Learns from context

## Create a Basic Agent

### Step 1: Create the Agent

```bash
abi-core add agent my-agent --description "My custom agent"
```

This creates:
```
agents/my-agent/
├── agent_my_agent.py    # Main code
├── main.py               # Entry point
├── models.py             # Data models
├── Dockerfile
└── requirements.txt
```

### Step 2: Understand the Code

Open `agents/my-agent/agent_my_agent.py`:

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class MyAgentAgent(AbiAgent):
    """My custom agent"""
    
    def __init__(self):
        super().__init__(
            agent_name='my-agent',
            description='My custom agent',
            content_types=['text/plain']
        )
        self.setup_llm()
    
    def setup_llm(self):
        """Configure the language model"""
        from langchain_ollama import ChatOllama
        import os
        
        model = os.getenv('MODEL_NAME', 'qwen2.5:3b')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        self.llm = ChatOllama(
            model=model,
            base_url=ollama_host,
            temperature=0.7
        )
    
    def process(self, enriched_input):
        """Process user input"""
        query = enriched_input['query']
        
        abi_logging(f"Processing: {query}")
        
        # Use LLM to generate response
        response = self.llm.invoke(query)
        
        return {
            'result': response.content,
            'query': query
        }
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Respond in streaming mode"""
        result = self.handle_input(query)
        
        yield {
            'content': result['result'],
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

## Customize Your Agent

### Change Temperature

Temperature controls creativity:

```python
def setup_llm(self):
    self.llm = ChatOllama(
        model='qwen2.5:3b',
        base_url=ollama_host,
        temperature=0.1  # More precise and deterministic
        # temperature=0.9  # More creative and varied
    )
```

**Examples**:
- `temperature=0.1`: For precise technical responses
- `temperature=0.5`: Balance between precision and creativity
- `temperature=0.9`: For creative content

### Add a System Prompt

```python
def setup_llm(self):
    from langchain_core.prompts import ChatPromptTemplate
    
    self.llm = ChatOllama(
        model='qwen2.5:3b',
        base_url=ollama_host,
        temperature=0.7
    )
    
    # Define agent behavior
    self.prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Python expert assistant. "
                   "Always respond with code examples."),
        ("human", "{input}")
    ])
    
    self.chain = self.prompt | self.llm

def process(self, enriched_input):
    query = enriched_input['query']
    
    # Use chain with prompt
    response = self.chain.invoke({"input": query})
    
    return {
        'result': response.content,
        'query': query
    }
```

### Add Input Validation

```python
def process(self, enriched_input):
    query = enriched_input['query']
    
    # Validate input
    if not query or len(query) < 3:
        return {
            'result': 'Please provide a more specific query.',
            'query': query,
            'error': 'Query too short'
        }
    
    if len(query) > 1000:
        return {
            'result': 'Query is too long. Maximum 1000 characters.',
            'query': query,
            'error': 'Query too long'
        }
    
    # Process normally
    response = self.llm.invoke(query)
    
    return {
        'result': response.content,
        'query': query
    }
```

## Test Your Agent

### Start the Agent

```bash
docker-compose up -d my-agent-agent
```

### Test with curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python?",
    "context_id": "test-001",
    "task_id": "task-001"
  }'
```

### Test with Python

```python
import requests

def test_agent(query):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": query,
            "context_id": "test-001",
            "task_id": "task-001"
        }
    )
    
    result = response.json()
    print(f"Question: {query}")
    print(f"Answer: {result['content']}")
    print("-" * 50)

# Test multiple queries
test_agent("What is Python?")
test_agent("Give me a function example")
test_agent("How to use a dictionary?")
```

## Specialized Agent Examples

### Math Agent

```python
class MathAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='math-agent',
            description='Solves math problems'
        )
        self.setup_llm()
    
    def setup_llm(self):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama
        
        self.llm = ChatOllama(
            model='qwen2.5:3b',
            temperature=0.1  # Mathematical precision
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are a math expert. "
             "Explain step by step how to solve each problem. "
             "Show all calculations."),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt | self.llm
```

### Code Agent

```python
class CodeAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='code-agent',
            description='Generates and explains code'
        )
        self.setup_llm()
    
    def setup_llm(self):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama
        
        self.llm = ChatOllama(
            model='qwen2.5:3b',
            temperature=0.2
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert programmer. "
             "Generate clean, well-documented code following best practices. "
             "Include explanatory comments. "
             "If there are errors, explain how to fix them."),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt | self.llm
```

## Debugging

### View Logs in Real-Time

```bash
docker-compose logs -f my-agent-agent
```

### Add Debug Points

```python
def process(self, enriched_input):
    import json
    
    # Log input
    abi_logging(f"INPUT: {json.dumps(enriched_input, indent=2)}")
    
    query = enriched_input['query']
    
    # Log before LLM
    abi_logging(f"Sending to LLM: {query}")
    
    response = self.llm.invoke(query)
    
    # Log response
    abi_logging(f"LLM Response: {response.content}")
    
    result = {
        'result': response.content,
        'query': query
    }
    
    # Log output
    abi_logging(f"OUTPUT: {json.dumps(result, indent=2)}")
    
    return result
```

### Test Locally (Without Docker)

```python
# test_local.py
from agents.my_agent.agent_my_agent import MyAgentAgent
import os

# Configure environment variables
os.environ['MODEL_NAME'] = 'qwen2.5:3b'
os.environ['OLLAMA_HOST'] = 'http://localhost:11434'

# Create agent
agent = MyAgentAgent()

# Test
result = agent.handle_input("Hello, how are you?")
print(result)
```

Run:
```bash
python test_local.py
```

## Next Steps

Now that you know how to create basic agents:

1. [Create a chatbot with interface](02-simple-chatbot.md)
2. [Add tools to your agent](03-agents-with-tools.md)
3. [Add conversational memory](04-agents-with-memory.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
