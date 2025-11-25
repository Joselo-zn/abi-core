# Descubrimiento de Agentes

Aprende cómo la capa semántica encuentra agentes automáticamente.

## Cómo Funciona

1. Agentes se registran con agent cards
2. Capa semántica indexa las cards
3. Búsquedas encuentran agentes por capacidad

## Buscar Agentes

```python
from abi_core.abi_mcp import client

# Buscar por tarea
agente = await client.find_agent(session, "analizar datos de ventas")

# Buscar múltiples
agentes = await client.recommend_agents(session, "procesar transacciones", max_agents=3)
```

## Próximos Pasos

- [Búsqueda semántica](03-semantic-search.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
