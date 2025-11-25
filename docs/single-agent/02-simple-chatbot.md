# Chatbot Simple

Aprende a crear un chatbot interactivo con interfaz web.

## Lo Que Vas a Construir

Un chatbot que:
- Responde preguntas en tiempo real
- Tiene interfaz web
- Mantiene contexto de conversación

## Paso 1: Crear el Agente con Interfaz Web

```bash
abi-core add agent chatbot \
  --description "Chatbot interactivo" \
  --with-web-interface
```

Esto crea archivos adicionales:
```
agents/chatbot/
├── agent_chatbot.py
├── main.py
├── web_interface.py    # ← Interfaz web
└── ...
```

## Paso 2: Código del Chatbot

Edita `agents/chatbot/agent_chatbot.py`:

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import os

class ChatbotAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='chatbot',
            description='Chatbot interactivo amigable'
        )
        self.setup_llm()
    
    def setup_llm(self):
        self.llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.7
        )
        
        # Prompt del sistema
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "Eres un asistente amigable y servicial. "
             "Respondes de forma clara y concisa. "
             "Si no sabes algo, lo admites honestamente."),
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

## Paso 3: Interfaz Web

El archivo `web_interface.py` ya está creado:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Chatbot API")

class Query(BaseModel):
    query: str
    context_id: str
    task_id: str

@app.post("/stream")
async def stream_response(query: Query):
    """Endpoint para consultas en streaming"""
    # El agente procesa y responde
    pass

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

## Paso 4: Iniciar el Chatbot

```bash
docker-compose up -d chatbot-agent
```

## Paso 5: Probar el Chatbot

### Interfaz Swagger

Abre en tu navegador:
```
http://localhost:8000/docs
```

Verás una interfaz interactiva donde puedes:
1. Expandir `/stream`
2. Click en "Try it out"
3. Ingresar tu consulta
4. Ver la respuesta

### Con curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hola, ¿cómo estás?",
    "context_id": "chat-001",
    "task_id": "msg-001"
  }'
```

### Cliente Python Simple

```python
import requests
import json

def chat(mensaje):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": mensaje,
            "context_id": "chat-001",
            "task_id": f"msg-{hash(mensaje)}"
        }
    )
    
    return response.json()['content']

# Usar el chatbot
print("Chatbot: Hola, ¿en qué puedo ayudarte?")

while True:
    user_input = input("Tú: ")
    if user_input.lower() in ['salir', 'exit', 'quit']:
        break
    
    respuesta = chat(user_input)
    print(f"Chatbot: {respuesta}")
```

## Personalizar el Chatbot

### Cambiar la Personalidad

```python
self.prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "Eres un experto en tecnología con sentido del humor. "
     "Usas analogías divertidas para explicar conceptos complejos. "
     "Siempre terminas con un emoji relevante."),
    ("human", "{input}")
])
```

### Agregar Respuestas Predefinidas

```python
def process(self, enriched_input):
    query = enriched_input['query'].lower()
    
    # Respuestas rápidas
    quick_responses = {
        'hola': '¡Hola! 👋 ¿En qué puedo ayudarte hoy?',
        'adiós': '¡Hasta luego! 👋 Que tengas un gran día.',
        'gracias': '¡De nada! 😊 Estoy aquí para ayudar.'
    }
    
    if query in quick_responses:
        return {
            'result': quick_responses[query],
            'query': query,
            'quick_response': True
        }
    
    # Respuesta normal con LLM
    response = self.chain.invoke({"input": query})
    
    return {
        'result': response.content,
        'query': query,
        'quick_response': False
    }
```

## Próximos Pasos

- [Agregar herramientas](03-agents-with-tools.md)
- [Agregar memoria](04-agents-with-memory.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
