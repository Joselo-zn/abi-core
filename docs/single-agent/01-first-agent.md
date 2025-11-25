# Tu Primer Agente

Ya creaste tu primer proyecto. Ahora aprenderás a crear y personalizar agentes de IA desde cero.

## ¿Qué es un Agente?

Un **agente** es un programa que:
- Entiende lenguaje natural
- Genera respuestas inteligentes
- Puede usar herramientas
- Aprende del contexto

## Crear un Agente Básico

### Paso 1: Crear el Agente

```bash
abi-core add agent mi-agente --description "Mi agente personalizado"
```

Esto crea:
```
agents/mi-agente/
├── agent_mi_agente.py    # Código principal
├── main.py               # Punto de entrada
├── models.py             # Modelos de datos
├── Dockerfile
└── requirements.txt
```

### Paso 2: Entender el Código

Abre `agents/mi-agente/agent_mi_agente.py`:

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class MiAgenteAgent(AbiAgent):
    """Mi agente personalizado"""
    
    def __init__(self):
        super().__init__(
            agent_name='mi-agente',
            description='Mi agente personalizado',
            content_types=['text/plain']
        )
        self.setup_llm()
    
    def setup_llm(self):
        """Configura el modelo de lenguaje"""
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
        """Procesa la entrada del usuario"""
        query = enriched_input['query']
        
        abi_logging(f"Procesando: {query}")
        
        # Usa el LLM para generar respuesta
        response = self.llm.invoke(query)
        
        return {
            'result': response.content,
            'query': query
        }
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Responde en streaming"""
        result = self.handle_input(query)
        
        yield {
            'content': result['result'],
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

## Personalizar Tu Agente

### Cambiar la Temperatura

La temperatura controla la creatividad:

```python
def setup_llm(self):
    self.llm = ChatOllama(
        model='qwen2.5:3b',
        base_url=ollama_host,
        temperature=0.1  # Más preciso y determinista
        # temperature=0.9  # Más creativo y variado
    )
```

**Ejemplos**:
- `temperature=0.1`: Para respuestas técnicas precisas
- `temperature=0.5`: Balance entre precisión y creatividad
- `temperature=0.9`: Para contenido creativo

### Agregar un Prompt del Sistema

```python
def setup_llm(self):
    from langchain_core.prompts import ChatPromptTemplate
    
    self.llm = ChatOllama(
        model='qwen2.5:3b',
        base_url=ollama_host,
        temperature=0.7
    )
    
    # Definir comportamiento del agente
    self.prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente experto en Python. "
                   "Siempre respondes con ejemplos de código."),
        ("human", "{input}")
    ])
    
    self.chain = self.prompt | self.llm

def process(self, enriched_input):
    query = enriched_input['query']
    
    # Usa el chain con el prompt
    response = self.chain.invoke({"input": query})
    
    return {
        'result': response.content,
        'query': query
    }
```

### Agregar Validación de Entrada

```python
def process(self, enriched_input):
    query = enriched_input['query']
    
    # Validar entrada
    if not query or len(query) < 3:
        return {
            'result': 'Por favor, proporciona una consulta más específica.',
            'query': query,
            'error': 'Query too short'
        }
    
    if len(query) > 1000:
        return {
            'result': 'La consulta es demasiado larga. Máximo 1000 caracteres.',
            'query': query,
            'error': 'Query too long'
        }
    
    # Procesar normalmente
    response = self.llm.invoke(query)
    
    return {
        'result': response.content,
        'query': query
    }
```

### Agregar Logging Detallado

```python
def process(self, enriched_input):
    query = enriched_input['query']
    
    abi_logging(f"[INICIO] Procesando consulta")
    abi_logging(f"[QUERY] {query}")
    
    try:
        response = self.llm.invoke(query)
        
        abi_logging(f"[RESPUESTA] {response.content[:100]}...")
        abi_logging(f"[ÉXITO] Consulta procesada correctamente")
        
        return {
            'result': response.content,
            'query': query,
            'status': 'success'
        }
    
    except Exception as e:
        abi_logging(f"[ERROR] {str(e)}")
        
        return {
            'result': 'Lo siento, ocurrió un error al procesar tu consulta.',
            'query': query,
            'status': 'error',
            'error': str(e)
        }
```

## Probar Tu Agente

### Iniciar el Agente

```bash
docker-compose up -d mi-agente-agent
```

### Probar con curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Qué es Python?",
    "context_id": "test-001",
    "task_id": "task-001"
  }'
```

### Probar con Python

```python
import requests

def probar_agente(query):
    response = requests.post(
        "http://localhost:8000/stream",
        json={
            "query": query,
            "context_id": "test-001",
            "task_id": "task-001"
        }
    )
    
    result = response.json()
    print(f"Pregunta: {query}")
    print(f"Respuesta: {result['content']}")
    print("-" * 50)

# Probar varias consultas
probar_agente("¿Qué es Python?")
probar_agente("Dame un ejemplo de función")
probar_agente("¿Cómo se usa un diccionario?")
```

## Ejemplos de Agentes Especializados

### Agente de Matemáticas

```python
class MathAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='math-agent',
            description='Resuelve problemas matemáticos'
        )
        self.setup_llm()
    
    def setup_llm(self):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama
        
        self.llm = ChatOllama(
            model='qwen2.5:3b',
            temperature=0.1  # Precisión matemática
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "Eres un experto en matemáticas. "
             "Explica paso a paso cómo resolver cada problema. "
             "Muestra todos los cálculos."),
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

### Agente de Traducción

```python
class TranslatorAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='translator',
            description='Traduce entre idiomas'
        )
        self.setup_llm()
    
    def setup_llm(self):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama
        
        self.llm = ChatOllama(
            model='qwen2.5:3b',
            temperature=0.3
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Eres un traductor profesional. "
             "Traduce el texto manteniendo el significado y tono original. "
             "Si no especifican el idioma destino, traduce al inglés."),
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

### Agente de Código

```python
class CodeAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='code-agent',
            description='Genera y explica código'
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
             "Eres un programador experto. "
             "Genera código limpio, bien documentado y siguiendo mejores prácticas. "
             "Incluye comentarios explicativos. "
             "Si hay errores, explica cómo corregirlos."),
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

## Depuración

### Ver Logs en Tiempo Real

```bash
docker-compose logs -f mi-agente-agent
```

### Agregar Puntos de Depuración

```python
def process(self, enriched_input):
    import json
    
    # Log de entrada
    abi_logging(f"INPUT: {json.dumps(enriched_input, indent=2)}")
    
    query = enriched_input['query']
    
    # Log antes de LLM
    abi_logging(f"Enviando a LLM: {query}")
    
    response = self.llm.invoke(query)
    
    # Log de respuesta
    abi_logging(f"Respuesta LLM: {response.content}")
    
    result = {
        'result': response.content,
        'query': query
    }
    
    # Log de salida
    abi_logging(f"OUTPUT: {json.dumps(result, indent=2)}")
    
    return result
```

### Probar Localmente (Sin Docker)

```python
# test_local.py
from agents.mi_agente.agent_mi_agente import MiAgenteAgent
import os

# Configurar variables de entorno
os.environ['MODEL_NAME'] = 'qwen2.5:3b'
os.environ['OLLAMA_HOST'] = 'http://localhost:11434'

# Crear agente
agent = MiAgenteAgent()

# Probar
result = agent.handle_input("Hola, ¿cómo estás?")
print(result)
```

Ejecutar:
```bash
python test_local.py
```

## Próximos Pasos

Ahora que sabes crear agentes básicos:

1. [Crear un chatbot con interfaz](02-simple-chatbot.md)
2. [Agregar herramientas a tu agente](03-agents-with-tools.md)
3. [Agregar memoria conversacional](04-agents-with-memory.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
