# Agent Cards (Tarjetas de Agente)

Las agent cards permiten que los agentes se descubran y comuniquen entre sí.

## ¿Qué es una Agent Card?

Una **agent card** es un documento JSON que describe:
- Nombre del agente
- Qué puede hacer
- Cómo contactarlo
- Qué tareas soporta

**Analogía**: Es como una tarjeta de presentación profesional.

## Crear una Agent Card

```bash
abi-core add agent-card analista \
  --description "Analiza datos de ventas" \
  --url "http://localhost:8000" \
  --tasks "analizar_ventas,generar_insights,calcular_metricas"
```

Esto crea:
```
services/semantic_layer/layer/mcp_server/agent_cards/analista.json
```

## Estructura de una Agent Card

```json
{
  "@context": ["https://..."],
  "@type": "Agent",
  "id": "agent://analista",
  "name": "analista",
  "description": "Analiza datos de ventas",
  "url": "http://localhost:8000",
  "supportedTasks": [
    "analizar_ventas",
    "generar_insights",
    "calcular_metricas"
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b"
  },
  "auth": {
    "method": "hmac_sha256",
    "key_id": "agent://analista-default",
    "shared_secret": "TOKEN_UNICO"
  }
}
```

## Campos Importantes

### id
Identificador único del agente:
```json
"id": "agent://analista"
```

### supportedTasks
Lista de tareas que el agente puede realizar:
```json
"supportedTasks": [
  "analizar_ventas",
  "generar_insights"
]
```

### url
Dirección donde se puede contactar al agente:
```json
"url": "http://localhost:8000"
```

### auth
Credenciales de autenticación:
```json
"auth": {
  "method": "hmac_sha256",
  "shared_secret": "TOKEN_SEGURO"
}
```

## Usar Agent Cards

### Buscar un Agente

```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def buscar_agente(tarea):
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host, config.port, config.transport
    ) as session:
        result = await client.find_agent(session, tarea)
        return result

# Buscar agente que pueda analizar ventas
agente = await buscar_agente("analizar datos de ventas")
print(agente)  # Retorna: analista
```

### Listar Todos los Agentes

```bash
curl http://localhost:10100/v1/agents
```

## Próximos Pasos

- [Comunicación entre agentes](03-agent-communication.md)
- [Tu primer sistema multi-agente](04-first-multi-agent-system.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
