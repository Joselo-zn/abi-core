# API Reference

Referencia completa de las APIs de ABI-Core.

## AbiAgent

Clase base para crear agentes.

```python
from abi_core.agent.agent import AbiAgent

class MiAgente(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='mi-agente',
            description='Descripción',
            content_types=['text/plain']
        )
```

### Métodos

#### `process(enriched_input)`
Procesa entrada enriquecida.

**Parámetros**:
- `enriched_input`: Dict con query y contexto

**Retorna**: Dict con resultado

#### `stream(query, context_id, task_id)`
Responde en streaming.

**Parámetros**:
- `query`: Consulta del usuario
- `context_id`: ID de contexto
- `task_id`: ID de tarea

**Retorna**: AsyncGenerator con respuestas

## MCP Client

Cliente para capa semántica.

```python
from abi_core.abi_mcp import client

async with client.init_session(host, port, transport) as session:
    result = await client.find_agent(session, "descripción")
```

### Funciones

#### `find_agent(session, description)`
Busca un agente por descripción.

#### `recommend_agents(session, description, max_agents)`
Recomienda múltiples agentes.

#### `check_agent_health(session, agent_name)`
Verifica salud de un agente.

## Utilidades

```python
from abi_core.common.utils import abi_logging, get_mcp_server_config

# Logging
abi_logging("Mensaje")

# Configuración MCP
config = get_mcp_server_config()
```

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
