# Extender la Capa Semántica

Personaliza y extiende la capa semántica según tus necesidades.

## Agregar Metadatos Personalizados

Edita agent cards para agregar información adicional:

```json
{
  "id": "agent://mi-agente",
  "metadata": {
    "domain": "finanzas",
    "region": "LATAM",
    "language": "es",
    "custom_field": "valor"
  }
}
```

## Filtrar por Metadatos

```python
# Buscar agentes de un dominio específico
agentes = await client.find_agents_by_metadata(
    session,
    {"domain": "finanzas"}
)
```

## Próximos Pasos

- [Orquestación avanzada](../orchestration/01-planner-orchestrator.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
