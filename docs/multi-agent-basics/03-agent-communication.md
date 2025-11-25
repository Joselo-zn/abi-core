# Comunicación Entre Agentes (A2A)

Aprende cómo los agentes se comunican entre sí usando el protocolo A2A.

## Protocolo A2A

**A2A** (Agent-to-Agent) es el protocolo que permite a los agentes:
- Enviarse mensajes
- Solicitar tareas
- Compartir resultados

## Comunicación Básica

### Agente A llama a Agente B

```python
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
import httpx
import json
from uuid import uuid4

async def llamar_agente(agent_card, mensaje):
    """Llama a otro agente"""
    async with httpx.AsyncClient() as http_client:
        a2a_client = A2AClient(http_client, agent_card)
        
        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{'kind': 'text', 'text': mensaje}],
                    'messageId': str(uuid4()),
                    'contextId': str(uuid4())
                }
            )
        )
        
        async for response in a2a_client.send_message_stream(request):
            if hasattr(response.root.result, 'artifact'):
                return response.root.result.artifact
```

## Ejemplo Completo

### Agente Coordinador

```python
from abi_core.agent.agent import AbiAgent
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

class CoordinadorAgent(AbiAgent):
    async def procesar_tarea_compleja(self, tarea):
        """Coordina múltiples agentes"""
        
        # 1. Buscar agente analista
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            result = await client.find_agent(
                session,
                "agente que analiza datos"
            )
            analista_card = AgentCard(**json.loads(result.content[0].text))
        
        # 2. Llamar al analista
        analisis = await llamar_agente(
            analista_card,
            f"Analiza: {tarea}"
        )
        
        # 3. Buscar agente reportero
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            result = await client.find_agent(
                session,
                "agente que genera reportes"
            )
            reportero_card = AgentCard(**json.loads(result.content[0].text))
        
        # 4. Llamar al reportero
        reporte = await llamar_agente(
            reportero_card,
            f"Genera reporte de: {analisis}"
        )
        
        return reporte
```

## Flujo de Comunicación

```
Usuario
  ↓
Coordinador
  ├─→ Analista → Resultado 1
  └─→ Reportero → Resultado 2
  ↓
Resultado Final
```

## Próximos Pasos

- [Tu primer sistema multi-agente](04-first-multi-agent-system.md)
- [Capa semántica](../semantic-layer/01-what-is-semantic-layer.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
