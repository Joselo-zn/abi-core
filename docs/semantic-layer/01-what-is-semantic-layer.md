# ¿Qué es la Capa Semántica?

La capa semántica es el "directorio inteligente" que permite descubrir agentes automáticamente.

## El Problema Sin Capa Semántica

```python
# Tienes que saber exactamente qué agente llamar
llamar_agente("http://analista:8000", "analiza datos")
llamar_agente("http://reportero:8001", "genera reporte")
# ¿Qué pasa si cambias las URLs?
# ¿Qué pasa si agregas nuevos agentes?
```

## La Solución: Capa Semántica

```python
# Busca automáticamente el agente correcto
agente = buscar_agente("necesito analizar datos")
# Retorna: Agente Analista

agente = buscar_agente("necesito generar un reporte")
# Retorna: Agente Reportero
```

## Componentes

### 1. MCP Server
Servidor que gestiona agent cards y búsquedas.

### 2. Weaviate
Base de datos vectorial para búsqueda semántica.

### 3. Agent Cards
Metadatos de cada agente.

## Agregar Capa Semántica

```bash
abi-core add semantic-layer
```

Esto crea:
```
services/semantic_layer/
├── layer/
│   ├── mcp_server/        # Servidor MCP
│   │   └── agent_cards/   # Tarjetas de agentes
│   └── embedding_mesh/    # Embeddings
├── Dockerfile
└── requirements.txt
```

## Usar la Capa Semántica

### Buscar Agente

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def buscar(descripcion):
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host, config.port, config.transport
    ) as session:
        result = await client.find_agent(session, descripcion)
        return result

# Buscar
agente = await buscar("agente que analiza ventas")
```

### Listar Agentes

```bash
curl http://localhost:10100/v1/agents
```

## Próximos Pasos

- [Descubrimiento de agentes](02-agent-discovery.md)
- [Búsqueda semántica](03-semantic-search.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
