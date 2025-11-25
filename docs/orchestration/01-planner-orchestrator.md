# Planner y Orchestrator

El Planner y Orchestrator coordinan workflows complejos con múltiples agentes.

## ¿Qué Hacen?

### Planner
- Divide tareas complejas en subtareas
- Encuentra agentes apropiados
- Crea plan de ejecución

### Orchestrator
- Ejecuta el plan
- Coordina agentes
- Sintetiza resultados

## Agregar Orchestration Layer

```bash
abi-core add agentic-orchestration-layer
```

Esto crea:
- Planner Agent (puerto 11437)
- Orchestrator Agent (puerto 8002)

## Usar el Sistema

```bash
# Enviar consulta compleja al Orchestrator
curl -X POST http://localhost:8083/stream \
  -d '{
    "query": "Analiza ventas del último mes y genera reporte",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

El Orchestrator:
1. Envía consulta al Planner
2. Planner crea plan con subtareas
3. Orchestrator ejecuta cada subtarea
4. Combina resultados

## Próximos Pasos

- [Workflows multi-agente](02-multi-agent-workflows.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
