# Variables de Entorno

Referencia completa de variables de entorno en ABI-Core.

## Agentes

### MODEL_NAME
Modelo LLM a usar.
```bash
MODEL_NAME=qwen2.5:3b
```

### OLLAMA_HOST
URL del servidor Ollama.
```bash
OLLAMA_HOST=http://localhost:11434
```

### AGENT_PORT
Puerto del agente.
```bash
AGENT_PORT=8000
```

### LOG_LEVEL
Nivel de logging.
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Semantic Layer

### SEMANTIC_LAYER_HOST
Host de la capa semántica.
```bash
SEMANTIC_LAYER_HOST=semantic-layer
```

### SEMANTIC_LAYER_PORT
Puerto de la capa semántica.
```bash
SEMANTIC_LAYER_PORT=10100
```

### TRANSPORT
Protocolo de transporte.
```bash
TRANSPORT=sse  # sse o http
```

## Guardian

### OPA_URL
URL del servidor OPA.
```bash
OPA_URL=http://guardian-opa:8181
```

### ABI_POLICY_PATH
Ruta a políticas OPA.
```bash
ABI_POLICY_PATH=/app/opa/policies
```

## Docker

### START_OLLAMA
Iniciar Ollama en el contenedor.
```bash
START_OLLAMA=false  # true o false
```

### LOAD_MODELS
Cargar modelos al iniciar.
```bash
LOAD_MODELS=false  # true o false
```

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
