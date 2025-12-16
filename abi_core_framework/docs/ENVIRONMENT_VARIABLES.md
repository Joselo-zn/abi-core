# Environment Variables Standard

## Regla de Oro

**Variables estáticas → Dockerfile**  
**Variables dinámicas → docker-compose.yaml**

## Variables por Categoría

### 🔒 Estáticas (Dockerfile)

Estas variables **NUNCA** cambian y se definen en el Dockerfile:

```dockerfile
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="Agent Name"
ENV ABI_NODE="ABI AGENT"
ENV AGENT_HOST=0.0.0.0
ENV SERVICE_MODULE=agent.main
ENV START_OLLAMA=false          # Default: centralizado
ENV LOAD_MODELS=false           # Default: centralizado
```

### 🔄 Dinámicas (docker-compose.yaml)

Estas variables **DEPENDEN** del proyecto/entorno y se definen en compose:

```yaml
environment:
  # Puertos (asignados dinámicamente)
  - AGENT_PORT=8002
  - SERVICE_PORT=8002
  - WEB_INTERFACE_PORT=8083     # Solo si tiene web interface
  
  # Conexión MCP (nombre del proyecto)
  - MCP_HOST=proyecto-semantic-layer
  - MCP_PORT=10100
  - MCP_TRANSPORT=sse
  
  # Modo Ollama (según configuración)
  - START_OLLAMA=true           # true=distribuido, false=centralizado
  - LOAD_MODELS=true            # true=distribuido, false=centralizado
  - OLLAMA_HOST=http://ollama:11434  # Solo si centralizado
```

## Aplicación por Tipo de Agente

### Planner & Orchestrator

**Dockerfile:**
```dockerfile
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="Planner Agent"
ENV ABI_NODE="ABI AGENT"
ENV AGENT_HOST=0.0.0.0
ENV SERVICE_MODULE=agent.main
ENV START_OLLAMA=false
ENV LOAD_MODELS=false
ENV SERVICE_PORT=11437          # Puerto por defecto
```

**Compose:**
```yaml
environment:
  - AGENT_PORT=11437            # Override si hay conflicto
  - SERVICE_PORT=11437
  - MCP_HOST=proyecto-semantic-layer
  - MCP_PORT=10100
  - MCP_TRANSPORT=sse
  - START_OLLAMA=false          # Override según modo
  - LOAD_MODELS=false
```

### Guardian

**Dockerfile:**
```dockerfile
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="Guardian Security Service"
ENV ABI_NODE="ABI SERVICE"
ENV AGENT_HOST=0.0.0.0
ENV SERVICE_MODULE=agent.main
ENV START_OLLAMA=false
ENV LOAD_MODELS=false
ENV SERVICE_PORT=11438
```

**Compose:**
```yaml
environment:
  - AGENT_PORT=11438
  - SERVICE_PORT=11438
  - MCP_HOST=proyecto-semantic-layer
  - MCP_PORT=10100
  - MCP_TRANSPORT=sse
  - START_OLLAMA=false
  - LOAD_MODELS=false
```

### Agentes Generados (CLI)

**Dockerfile (template):**
```dockerfile
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="{{ agent_name }} Agent"
ENV ABI_NODE="ABI AGENT"
ENV AGENT_HOST=0.0.0.0
ENV SERVICE_MODULE=main
ENV START_OLLAMA=false
ENV LOAD_MODELS=false
ENV SERVICE_PORT={{ agent_port }}
```

**Compose:**
```yaml
environment:
  - AGENT_PORT={{ agent_port }}
  - SERVICE_PORT={{ agent_port }}
  - WEB_INTERFACE_PORT={{ web_port }}  # Si tiene web interface
  - MCP_HOST=proyecto-semantic-layer
  - MCP_PORT=10100
  - MCP_TRANSPORT=sse
  - START_OLLAMA={{ 'true' if distributed else 'false' }}
  - LOAD_MODELS={{ 'true' if distributed else 'false' }}
```

## ❌ Anti-Patrones

**NO hacer:**

```yaml
# ❌ Duplicar variables estáticas en compose
environment:
  - PYTHONPATH=/app              # Ya está en Dockerfile
  - PYTHONUNBUFFERED=1           # Ya está en Dockerfile
  - ABI_ROLE=Planner Agent       # Ya está en Dockerfile
  - SERVICE_MODULE=agent.main    # Ya está en Dockerfile
```

**SÍ hacer:**

```yaml
# ✅ Solo variables dinámicas en compose
environment:
  - AGENT_PORT=11437             # Dinámico
  - MCP_HOST=proyecto-semantic   # Dinámico
  - START_OLLAMA=false           # Override según modo
```

## Verificación

Para verificar que no hay duplicación:

```bash
# Ver variables del Dockerfile
grep "^ENV" Dockerfile

# Ver variables del compose
grep -A 20 "environment:" docker-compose.yml
```

Si una variable aparece en ambos lugares, **eliminarla del compose** a menos que sea un override intencional.

## Excepciones

Las únicas variables que pueden aparecer en ambos lugares son:

1. **START_OLLAMA** - Default en Dockerfile, override en compose según modo
2. **LOAD_MODELS** - Default en Dockerfile, override en compose según modo
3. **Puertos** - Default en Dockerfile, override en compose si hay conflicto

En estos casos, el compose **sobrescribe** el valor del Dockerfile.
