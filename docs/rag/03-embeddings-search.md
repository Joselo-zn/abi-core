# Embeddings y Búsqueda

Los embeddings convierten texto en vectores numéricos para búsqueda semántica.

## ¿Qué son Embeddings?

```
"Python es genial" → [0.2, 0.8, 0.1, 0.5, ...]
"Python es excelente" → [0.3, 0.7, 0.2, 0.4, ...]
# Vectores similares = significado similar
```

## Modelo de Embeddings

ABI-Core usa `nomic-embed-text:v1.5` automáticamente.

## Búsqueda Semántica

```python
# Buscar documentos similares
query = "lenguaje de programación"
results = buscar_similares(query)
# Encuentra: "Python", "JavaScript", "Java"
```

## Próximos Pasos

- [Agentes con RAG](04-agents-with-rag.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
