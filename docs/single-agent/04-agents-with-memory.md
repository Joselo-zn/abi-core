# Agentes con Memoria

Aprende a crear agentes que recuerdan conversaciones anteriores.

## ¿Por Qué Memoria?

Sin memoria:
```
Usuario: "Mi nombre es Ana"
Agente: "Hola Ana"
Usuario: "¿Cuál es mi nombre?"
Agente: "No lo sé"  ❌
```

Con memoria:
```
Usuario: "Mi nombre es Ana"
Agente: "Hola Ana"
Usuario: "¿Cuál es mi nombre?"
Agente: "Tu nombre es Ana"  ✅
```

## Implementar Memoria

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
            description='Agente con memoria conversacional'
        )
        self.conversations = {}  # Memoria por context_id
        self.setup_llm()
    
    def setup_llm(self):
        self.llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.7
        )
    
    def get_conversation(self, context_id: str):
        """Obtiene o crea conversación para un contexto"""
        if context_id not in self.conversations:
            memory = ConversationBufferMemory()
            self.conversations[context_id] = ConversationChain(
                llm=self.llm,
                memory=memory,
                verbose=True
            )
        return self.conversations[context_id]
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Responde con memoria"""
        conversation = self.get_conversation(context_id)
        response = conversation.predict(input=query)
        
        yield {
            'content': response,
            'response_type': 'text',
            'is_task_completed': True
        }
```

## Probar Memoria

```python
import requests

def chat(mensaje, context_id="conv-001"):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": mensaje,
            "context_id": context_id,
            "task_id": f"msg-{hash(mensaje)}"
        }
    )
    return response.json()['content']

# Conversación con memoria
print(chat("Mi nombre es Carlos"))
# "Hola Carlos, ¿en qué puedo ayudarte?"

print(chat("¿Cuál es mi nombre?"))
# "Tu nombre es Carlos"

print(chat("Tengo 30 años"))
# "Entendido, tienes 30 años"

print(chat("¿Cuántos años tengo?"))
# "Tienes 30 años"
```

## Tipos de Memoria

### Buffer Memory (Simple)
```python
from langchain.memory import ConversationBufferMemory
memory = ConversationBufferMemory()
```

### Window Memory (Últimos N mensajes)
```python
from langchain.memory import ConversationBufferWindowMemory
memory = ConversationBufferWindowMemory(k=5)  # Últimos 5 mensajes
```

### Summary Memory (Resumen)
```python
from langchain.memory import ConversationSummaryMemory
memory = ConversationSummaryMemory(llm=llm)
```

## Próximos Pasos

- [Probar agentes](05-testing-agents.md)
- [Múltiples agentes](../multi-agent-basics/01-why-multiple-agents.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
