# Manejo de Dependencias

Gestiona dependencias entre tareas en workflows complejos.

## Dependencias

Una tarea puede depender de otras:

```python
{
    "task_id": "generar_reporte",
    "dependencies": ["recolectar_datos", "analizar_datos"]
}
```

El Orchestrator ejecuta tareas solo cuando sus dependencias están completas.

## Próximos Pasos

- [Síntesis de resultados](04-result-synthesis.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
