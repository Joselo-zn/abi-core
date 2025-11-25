# Environment Variables

Complete reference for environment variables in ABI-Core.

## Agents

### MODEL_NAME
LLM model to use.
```bash
MODEL_NAME=qwen2.5:3b
```

### OLLAMA_HOST
Ollama server URL.
```bash
OLLAMA_HOST=http://localhost:11434
```

### AGENT_PORT
Agent port.
```bash
AGENT_PORT=8000
```

### LOG_LEVEL
Logging level.
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Semantic Layer

### SEMANTIC_LAYER_HOST
Semantic layer host.
```bash
SEMANTIC_LAYER_HOST=semantic-layer
```

### SEMANTIC_LAYER_PORT
Semantic layer port.
```bash
SEMANTIC_LAYER_PORT=10100
```

### TRANSPORT
Transport protocol.
```bash
TRANSPORT=sse  # sse or http
```

## Guardian

### OPA_URL
OPA server URL.
```bash
OPA_URL=http://guardian-opa:8181
```

### ABI_POLICY_PATH
Path to OPA policies.
```bash
ABI_POLICY_PATH=/app/opa/policies
```

## Docker

### START_OLLAMA
Start Ollama in container.
```bash
START_OLLAMA=false  # true or false
```

### LOAD_MODELS
Load models on startup.
```bash
LOAD_MODELS=false  # true or false
```

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
