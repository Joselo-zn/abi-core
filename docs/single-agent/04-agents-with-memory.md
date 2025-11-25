# Agents with Memory

Learn to create agents that remember previous conversations.

## Why Memory?

Without memory:
```
User: "My name is Ana"
Agent: "Hello Ana"
User: "What's my name?"
Agent: "I don't know"  ❌
```

With memory:
```
User: "My name is Ana"
Agent: "Hello Ana"
User: "What's my name?"
Agent: "Your name is Ana"  ✅
```

## Implement Memory

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
import os

class MemoryAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='memory-agent',
            description='Agent with conversational memory'
        )
        self.conversations = {}  # Memory by context_id
        self.setup_llm()
    
    def setup_llm(self):
        self.llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.7
        )
    
    def get_conversation(self, context_id: str):
        """Get or create conversation for a context"""
        if context_id not in self.conversations:
            memory = ConversationBufferMemory()
            self.conversations[context_id] = ConversationChain(
                llm=self.llm,
                memory=memory,
                verbose=True
            )
        return self.conversations[context_id]
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Respond with memory"""
        conversation = self.get_conversation(context_id)
        response = conversation.predict(input=query)
        
        yield {
            'content': response,
            'response_type': 'text',
            'is_task_completed': True
        }
```

## Test Memory

```python
import requests

def chat(message, context_id="conv-001"):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": message,
            "context_id": context_id,
            "task_id": f"msg-{hash(message)}"
        }
    )
    return response.json()['content']

# Conversation with memory
print(chat("My name is Carlos"))
# "Hello Carlos, how can I help you?"

print(chat("What's my name?"))
# "Your name is Carlos"

print(chat("I'm 30 years old"))
# "Understood, you're 30 years old"

print(chat("How old am I?"))
# "You're 30 years old"
```

## Memory Types

### Buffer Memory (Simple)
```python
from langchain.memory import ConversationBufferMemory
memory = ConversationBufferMemory()
```

### Window Memory (Last N messages)
```python
from langchain.memory import ConversationBufferWindowMemory
memory = ConversationBufferWindowMemory(k=5)  # Last 5 messages
```

### Summary Memory (Summary)
```python
from langchain.memory import ConversationSummaryMemory
memory = ConversationSummaryMemory(llm=llm)
```

## Next Steps

- [Test agents](05-testing-agents.md)
- [Multiple agents](../multi-agent-basics/01-why-multiple-agents.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
