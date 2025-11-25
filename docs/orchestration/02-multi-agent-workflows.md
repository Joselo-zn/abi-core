# Workflows Multi-Agente

Crea workflows complejos que coordinan múltiples agentes.

## Tipos de Workflows

### Secuencial
```
Agente 1 → Agente 2 → Agente 3
```

### Paralelo
```
Agente 1 →
Agente 2 → Combinar resultados
Agente 3 →
```

### Híbrido
```
Agente 1 → Agente 2 →
                      → Agente 4
Agente 3 ────────────→
```

## Ejemplo de Workflow

```python
# El Planner crea este plan
plan = {
    "tasks": [
        {"id": "task_1", "agent": "recolector", "dependencies": []},
        {"id": "task_2", "agent": "analista", "dependencies": ["task_1"]},
        {"id": "task_3", "agent": "reportero", "dependencies": ["task_2"]}
    ]
}

# El Orchestrator lo ejecuta
```

## Próximos Pasos

- [Manejo de dependencias](03-dependency-management.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
