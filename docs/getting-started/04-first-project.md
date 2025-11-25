# Tu Primer Proyecto

En esta guía crearás tu primer proyecto con ABI-Core paso a paso. Al final tendrás un agente funcionando que puedes consultar.

## Lo Que Vas a Construir

Un proyecto simple con:
- ✅ Un agente de IA
- ✅ Modelo de lenguaje (qwen2.5:3b)
- ✅ Interfaz para consultas

**Tiempo estimado**: 10 minutos

## Paso 1: Crear el Proyecto

Abre tu terminal y ejecuta:

```bash
abi-core create project mi-primer-proyecto
```

**¿Qué hace este comando?**
- Crea la estructura de directorios
- Configura Docker
- Prepara el entorno

**Salida esperada**:
```
🚀 Creating ABI project: mi-primer-proyecto
✅ Project structure created
✅ Docker configuration created
✅ Runtime configuration created

📁 Project created at: ./mi-primer-proyecto

Next steps:
  cd mi-primer-proyecto
  abi-core provision-models
```

## Paso 2: Navegar al Proyecto

```bash
cd mi-primer-proyecto
```

**Estructura creada**:
```
mi-primer-proyecto/
├── agents/              # Aquí irán tus agentes
├── services/            # Servicios de soporte
├── compose.yaml         # Configuración Docker
├── .abi/
│   └── runtime.yaml     # Configuración del proyecto
└── README.md
```

## Paso 3: Provisionar Modelos

Este paso descarga el modelo de IA que usará tu agente:

```bash
abi-core provision-models
```

**¿Qué hace este comando?**
1. Inicia el servicio Ollama
2. Descarga `qwen2.5:3b` (~2GB)
3. Descarga modelo de embeddings
4. Actualiza la configuración

**Salida esperada**:
```
🚀 Starting model provisioning...
📦 Model serving mode: centralized
🔄 Starting Ollama service...
✅ Ollama service started

📥 Downloading qwen2.5:3b...
████████████████████████████ 100%
✅ qwen2.5:3b downloaded successfully

📥 Downloading nomic-embed-text:v1.5...
████████████████████████████ 100%
✅ nomic-embed-text:v1.5 downloaded successfully

✅ Models provisioned successfully
```

**Nota**: La primera vez toma varios minutos dependiendo de tu conexión.

## Paso 4: Crear Tu Primer Agente

Ahora crea un agente:

```bash
abi-core add agent asistente --description "Mi primer agente de IA"
```

**¿Qué hace este comando?**
- Crea el código del agente
- Configura el Dockerfile
- Registra el agente en el proyecto

**Salida esperada**:
```
✅ Agent 'asistente' added successfully!
📁 Location: agents/asistente
🚀 Port: 8000
📦 Docker service added to compose file
```

**Archivos creados**:
```
agents/asistente/
├── __init__.py
├── agent_asistente.py    # Código del agente
├── main.py               # Punto de entrada
├── models.py             # Modelos de datos
├── Dockerfile            # Configuración Docker
└── requirements.txt      # Dependencias
```

## Paso 5: Iniciar el Sistema

Inicia todos los servicios:

```bash
abi-core run
```

O con Docker Compose directamente:

```bash
docker-compose up -d
```

**¿Qué se inicia?**
- Servicio Ollama (modelos de IA)
- Tu agente asistente

**Verificar que está funcionando**:
```bash
docker-compose ps
```

Deberías ver:
```
NAME                          STATUS    PORTS
mi-primer-proyecto-ollama     Up        0.0.0.0:11434->11434/tcp
asistente-agent               Up        0.0.0.0:8000->8000/tcp
```

## Paso 6: Probar Tu Agente

### Opción 1: Con curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hola, ¿cómo estás?",
    "context_id": "test-001",
    "task_id": "task-001"
  }'
```

**Respuesta esperada**:
```json
{
  "content": "¡Hola! Estoy bien, gracias por preguntar. Soy tu asistente de IA. ¿En qué puedo ayudarte hoy?",
  "response_type": "text",
  "is_task_completed": true
}
```

### Opción 2: Con Python

Crea un archivo `test_agent.py`:

```python
import requests

response = requests.post(
    "http://localhost:8000/stream",
    json={
        "query": "¿Qué es la inteligencia artificial?",
        "context_id": "test-001",
        "task_id": "task-001"
    }
)

print(response.json())
```

Ejecuta:
```bash
python test_agent.py
```

### Opción 3: Navegador

Abre tu navegador y ve a:
```
http://localhost:8000/docs
```

Verás la interfaz Swagger donde puedes probar el agente interactivamente.

## Paso 7: Ver Logs

Para ver qué está haciendo tu agente:

```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver solo logs del agente
docker-compose logs -f asistente-agent

# Ver solo logs de Ollama
docker-compose logs -f mi-primer-proyecto-ollama
```

## Paso 8: Detener el Sistema

Cuando termines:

```bash
# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (modelos)
docker-compose down -v
```

## Entendiendo Tu Proyecto

### Archivo: `agents/asistente/agent_asistente.py`

Este es el código principal de tu agente:

```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class AsistenteAgent(AbiAgent):
    """Mi primer agente de IA"""
    
    def __init__(self):
        super().__init__(
            agent_name='asistente',
            description='Mi primer agente de IA',
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
        """Procesa la consulta del usuario"""
        query = enriched_input['query']
        
        abi_logging(f"Procesando: {query}")
        
        # Usa el LLM para generar respuesta
        response = self.llm.invoke(query)
        
        return {
            'result': response.content,
            'query': query
        }
    
    async def stream(self, query: str, context_id: str, task_id: str):
        """Responde a consultas en streaming"""
        
        # Procesa con enriquecimiento semántico
        result = self.handle_input(query)
        
        # Retorna respuesta
        yield {
            'content': result['result'],
            'response_type': 'text',
            'is_task_completed': True,
            'require_user_input': False
        }
```

### Archivo: `.abi/runtime.yaml`

Configuración del proyecto:

```yaml
project:
  name: mi-primer-proyecto
  domain: general
  model_serving: centralized

agents:
  asistente:
    name: Asistente
    description: Mi primer agente de IA
    model: qwen2.5:3b
    port: 8000
    path: agents/asistente

models:
  llm:
    name: qwen2.5:3b
    provisioned: true
  embedding:
    name: nomic-embed-text:v1.5
    provisioned: true
```

### Archivo: `compose.yaml`

Configuración de Docker:

```yaml
services:
  mi-primer-proyecto-ollama:
    image: ollama/ollama:latest
    container_name: mi-primer-proyecto-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - mi-primer-proyecto-network
  
  asistente-agent:
    build: ./agents/asistente
    container_name: asistente-agent
    ports:
      - "8000:8000"
    environment:
      - MODEL_NAME=qwen2.5:3b
      - OLLAMA_HOST=http://mi-primer-proyecto-ollama:11434
    depends_on:
      - mi-primer-proyecto-ollama
    networks:
      - mi-primer-proyecto-network

volumes:
  ollama_data:

networks:
  mi-primer-proyecto-network:
    driver: bridge
```

## Personalizar Tu Agente

### Cambiar el Modelo

Edita `.abi/runtime.yaml`:

```yaml
agents:
  asistente:
    model: llama3.2:3b  # Cambiar a otro modelo
```

Descarga el nuevo modelo:
```bash
docker exec mi-primer-proyecto-ollama ollama pull llama3.2:3b
```

Reinicia:
```bash
docker-compose restart asistente-agent
```

### Cambiar el Puerto

Edita `compose.yaml`:

```yaml
asistente-agent:
  ports:
    - "9000:8000"  # Cambiar puerto externo
```

Reinicia:
```bash
docker-compose up -d
```

### Modificar el Comportamiento

Edita `agents/asistente/agent_asistente.py`:

```python
def setup_llm(self):
    self.llm = ChatOllama(
        model='qwen2.5:3b',
        base_url=ollama_host,
        temperature=0.1  # Más determinista
        # temperature=0.9  # Más creativo
    )
```

Reconstruye:
```bash
docker-compose up -d --build asistente-agent
```

## Solución de Problemas

### Error: "Port already in use"

**Causa**: El puerto 8000 ya está en uso.

**Solución**: Cambia el puerto en `compose.yaml` o detén el servicio que lo usa.

### Error: "Model not found"

**Causa**: El modelo no se descargó correctamente.

**Solución**:
```bash
docker exec mi-primer-proyecto-ollama ollama pull qwen2.5:3b
```

### Error: "Connection refused"

**Causa**: Ollama no está funcionando.

**Solución**:
```bash
docker-compose restart mi-primer-proyecto-ollama
docker-compose logs mi-primer-proyecto-ollama
```

### El agente responde muy lento

**Causa**: El modelo es grande para tu hardware.

**Solución**: Usa un modelo más pequeño:
```bash
docker exec mi-primer-proyecto-ollama ollama pull phi3:mini
```

Actualiza la configuración para usar `phi3:mini`.

## Próximos Pasos

¡Felicidades! Ya tienes tu primer proyecto funcionando. Ahora puedes:

1. [Crear un chatbot más complejo](../single-agent/02-simple-chatbot.md)
2. [Agregar herramientas a tu agente](../single-agent/03-agents-with-tools.md)
3. [Agregar memoria conversacional](../single-agent/04-agents-with-memory.md)

## Resumen

En esta guía aprendiste a:

- ✅ Crear un proyecto con `abi-core create project`
- ✅ Provisionar modelos con `abi-core provision-models`
- ✅ Crear un agente con `abi-core add agent`
- ✅ Iniciar el sistema con `abi-core run`
- ✅ Probar tu agente con HTTP
- ✅ Ver logs y depurar
- ✅ Personalizar configuración

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
