# Embeddings and Search

Embeddings convert text to numerical vectors for semantic search.

## What are Embeddings?

```
"Python is great" → [0.2, 0.8, 0.1, 0.5, ...]
"Python is excellent" → [0.3, 0.7, 0.2, 0.4, ...]
# Similar vectors = similar meaning
```

## Embedding Model

ABI-Core uses `nomic-embed-text:v1.5` automatically.

## Semantic Search

```python
# Search for similar documents
query = "programming language"
results = search_similar(query)
# Finds: "Python", "JavaScript", "Java"
```

## Next Steps

- [Agents with RAG](04-agents-with-rag.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
