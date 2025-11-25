# Agentes con Herramientas

Los agentes pueden usar herramientas para realizar acciones específicas como calcular, buscar información o llamar APIs.

## ¿Qué son las Herramientas?

Las **herramientas** (tools) son funciones que el agente puede llamar para:
- Realizar cálculos
- Buscar información
- Llamar APIs externas
- Acceder a bases de datos

## Crear un Agente con Herramientas

### Paso 1: Definir Herramientas

```python
from langchain.tools import tool

@tool
def calcular(expresion: str) -> str:
    """Calcula una expresión matemática"""
    try:
        resultado = eval(expresion)
        return f"Resultado: {resultado}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def obtener_clima(ciudad: str) -> str:
    """Obtiene el clima de una ciudad"""
    # En producción, llamarías a una API real
    return f"El clima en {ciudad} es soleado, 22°C"

@tool
def buscar_web(query: str) -> str:
    """Busca información en la web"""
    # En producción, usarías una API de búsqueda
    return f"Resultados para '{query}': [información simulada]"
```

### Paso 2: Crear el Agente

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
import os

class ToolAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='tool-agent',
            description='Agente con herramientas'
        )
        self.setup_agent_with_tools()
    
    def setup_agent_with_tools(self):
        # LLM
        llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.1
        )
        
        # Herramientas
        tools = [calcular, obtener_clima, buscar_web]
        
        # Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Eres un asistente con acceso a herramientas. "
                       "Usa las herramientas cuando sea necesario."),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        # Crear agente
        agent = create_tool_calling_agent(llm, tools, prompt)
        
        # Executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True
        )
    
    def process(self, enriched_input):
        query = enriched_input['query']
        
        # Ejecutar con herramientas
        result = self.agent_executor.invoke({"input": query})
        
        return {
            'result': result['output'],
            'query': query
        }
```

## Ejemplos de Uso

```bash
# Calcular
curl -X POST http://localhost:8000/stream \
  -d '{"query": "¿Cuánto es 25 * 4?", "context_id": "test", "task_id": "1"}'
# Respuesta: "Resultado: 100"

# Clima
curl -X POST http://localhost:8000/stream \
  -d '{"query": "¿Qué clima hace en Madrid?", "context_id": "test", "task_id": "2"}'
# Respuesta: "El clima en Madrid es soleado, 22°C"

# Búsqueda
curl -X POST http://localhost:8000/stream \
  -d '{"query": "Busca información sobre Python", "context_id": "test", "task_id": "3"}'
```

## Herramientas Avanzadas

### Herramienta con API Real

```python
@tool
def obtener_precio_crypto(simbolo: str) -> str:
    """Obtiene el precio actual de una criptomoneda"""
    import requests
    
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': simbolo.lower(),
            'vs_currencies': 'usd'
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        precio = data[simbolo.lower()]['usd']
        return f"El precio de {simbolo} es ${precio} USD"
    except Exception as e:
        return f"Error obteniendo precio: {str(e)}"
```

### Herramienta con Base de Datos

```python
@tool
def consultar_usuario(user_id: str) -> str:
    """Consulta información de un usuario"""
    import sqlite3
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name, email FROM users WHERE id = ?",
            (user_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return f"Usuario: {result[0]}, Email: {result[1]}"
        else:
            return f"Usuario {user_id} no encontrado"
    except Exception as e:
        return f"Error: {str(e)}"
```

## Próximos Pasos

- [Agregar memoria](04-agents-with-memory.md)
- [Probar agentes](05-testing-agents.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
