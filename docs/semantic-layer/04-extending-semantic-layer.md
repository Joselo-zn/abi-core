# Extending the Semantic Layer

Customize and extend the semantic layer for your needs.

## Add Custom Metadata

Edit agent cards to add additional information:

```json
{
  "id": "agent://my-agent",
  "metadata": {
    "domain": "finance",
    "region": "LATAM",
    "language": "en",
    "custom_field": "value"
  }
}
```

## Filter by Metadata

```python
# Search agents from a specific domain
agents = await client.find_agents_by_metadata(
    session,
    {"domain": "finance"}
)
```

## Next Steps

- [Advanced orchestration](../orchestration/01-planner-orchestrator.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
