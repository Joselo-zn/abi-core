# Semantic Search

Semantic search finds agents by meaning, not just exact words.

## Word Search vs Semantic

### Word Search
```
Search: "analyze sales"
Finds: Only agents with "analyze" AND "sales"
```

### Semantic Search
```
Search: "examine revenue"
Finds: Sales analysis agent
(Understands "examine" ≈ "analyze" and "revenue" ≈ "sales")
```

## How It Works

1. Text → Embeddings (numerical vectors)
2. Search by vector similarity
3. Returns most relevant agents

## Use Semantic Search

```python
# Different ways to ask for the same thing
await client.find_agent(session, "analyze sales data")
await client.find_agent(session, "examine revenue information")
await client.find_agent(session, "review commercial statistics")
# All find the same agent
```

## Next Steps

- [Extend semantic layer](04-extending-semantic-layer.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
