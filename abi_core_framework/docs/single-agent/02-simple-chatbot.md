# Simple Chatbot

Learn to create an interactive chatbot with a web interface.

## What You'll Build

A chatbot that:
- Responds to questions in real-time
- Has a web interface
- Maintains conversation context

## Step 1: Create Agent with Web Interface

```bash
abi-core add agent chatbot \
  --description "Interactive chatbot" \
  --with-web-interface
```

This creates additional files:
```
agents/chatbot/
├── agent_chatbot.py
├── main.py
├── web_interface.py    # ← Web interface
└── ...
```

## Step 2: Chatbot Code

Edit `agents/chatbot/agent_chatbot.py`:

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import os

class ChatbotAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='chatbot',
            description='Friendly interactive chatbot'
        )
        self.setup_llm()
    
    def setup_llm(self):
        self.llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.7
        )
        
        # System prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are a friendly and helpful assistant. "
             "Respond clearly and concisely. "
             "If you don't know something, admit it honestly."),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt | self.llm
    
    def process(self, enriched_input):
        query = enriched_input['query']
        response = self.chain.invoke({"input": query})
        
        return {
            'result': response.content,
            'query': query
        }
```

## Step 3: Start the Chatbot

```bash
docker-compose up -d chatbot-agent
```

## Step 4: Test the Chatbot

### Swagger Interface

Open in your browser:
```
http://localhost:8000/docs
```

You'll see an interactive interface where you can:
1. Expand `/stream`
2. Click "Try it out"
3. Enter your query
4. See the response

### With curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, how are you?",
    "context_id": "chat-001",
    "task_id": "msg-001"
  }'
```

### Simple Python Client

```python
import requests
import json

def chat(message):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": message,
            "context_id": "chat-001",
            "task_id": f"msg-{hash(message)}"
        }
    )
    
    return response.json()['content']

# Use the chatbot
print("Chatbot: Hello, how can I help you?")

while True:
    user_input = input("You: ")
    if user_input.lower() in ['exit', 'quit', 'bye']:
        break
    
    response = chat(user_input)
    print(f"Chatbot: {response}")
```

## Customize the Chatbot

### Change Personality

```python
self.prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a tech expert with a sense of humor. "
     "Use funny analogies to explain complex concepts. "
     "Always end with a relevant emoji."),
    ("human", "{input}")
])
```

### Add Quick Responses

```python
def process(self, enriched_input):
    query = enriched_input['query'].lower()
    
    # Quick responses
    quick_responses = {
        'hello': '👋 Hello! How can I help you today?',
        'bye': '👋 Goodbye! Have a great day.',
        'thanks': '😊 You're welcome! I'm here to help.'
    }
    
    if query in quick_responses:
        return {
            'result': quick_responses[query],
            'query': query,
            'quick_response': True
        }
    
    # Normal LLM response
    response = self.chain.invoke({"input": query})
    
    return {
        'result': response.content,
        'query': query,
        'quick_response': False
    }
```

## Next Steps

- [Add tools](03-agents-with-tools.md)
- [Add memory](04-agents-with-memory.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
