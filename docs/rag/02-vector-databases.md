# Vector Databases

Vector databases store and search information by semantic similarity.

## Weaviate in ABI-Core

ABI-Core uses **Weaviate** automatically when you add the semantic layer.

```bash
abi-core add semantic-layer
# Weaviate is included automatically
```

## How It Works

1. Documents → Embeddings (vectors)
2. Store in Weaviate
3. Search by vector similarity

## Use Weaviate

```python
import weaviate

# Connect
client = weaviate.Client("http://localhost:8080")

# Add document
client.data_object.create({
    "content": "Python is a programming language",
    "category": "technology"
}, "Document")

# Search
result = client.query.get("Document", ["content"]).with_near_text({
    "concepts": ["programming language"]
}).do()
```

## Next Steps

- [Embeddings and search](03-embeddings-search.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
