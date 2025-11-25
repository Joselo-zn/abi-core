# Bases de Datos Vectoriales

Las bases de datos vectoriales almacenan y buscan información por similitud semántica.

## Weaviate en ABI-Core

ABI-Core usa **Weaviate** automáticamente cuando agregas la capa semántica.

```bash
abi-core add semantic-layer
# Weaviate se incluye automáticamente
```

## Cómo Funciona

1. Documentos → Embeddings (vectores)
2. Almacenar en Weaviate
3. Buscar por similitud vectorial

## Usar Weaviate

```python
import weaviate

# Conectar
client = weaviate.Client("http://localhost:8080")

# Agregar documento
client.data_object.create({
    "content": "Python es un lenguaje de programación",
    "category": "tecnología"
}, "Document")

# Buscar
result = client.query.get("Document", ["content"]).with_near_text({
    "concepts": ["lenguaje de programación"]
}).do()
```

## Próximos Pasos

- [Embeddings y búsqueda](03-embeddings-search.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
