# ¿Qué es RAG?

RAG (Retrieval-Augmented Generation) permite a los agentes acceder a información específica de tu dominio.

## El Problema

Los LLMs tienen conocimiento general pero no saben sobre:
- Tus productos específicos
- Tus documentos internos
- Información actualizada

## La Solución: RAG

RAG = Recuperar información relevante + Generar respuesta

```
Usuario: "¿Cuál es el precio del producto X?"
  ↓
1. Buscar en base de datos → "Producto X: $99"
2. LLM genera respuesta → "El producto X cuesta $99"
```

## Componentes de RAG

### 1. Base de Datos Vectorial
Almacena documentos como vectores (Weaviate en ABI-Core).

### 2. Embeddings
Convierte texto en vectores numéricos.

### 3. Búsqueda Semántica
Encuentra documentos relevantes.

### 4. LLM
Genera respuesta usando documentos encontrados.

## Flujo RAG

```
Pregunta del usuario
  ↓
Convertir a embedding
  ↓
Buscar documentos similares
  ↓
Pasar documentos + pregunta al LLM
  ↓
Respuesta generada
```

## Cuándo Usar RAG

✅ Usar RAG cuando:
- Necesitas información específica de tu dominio
- Tienes documentos/manuales/políticas
- Quieres respuestas basadas en tus datos

❌ No usar RAG cuando:
- Solo necesitas conocimiento general
- No tienes documentos para indexar

## Próximos Pasos

- [Bases de datos vectoriales](02-vector-databases.md)
- [Embeddings y búsqueda](03-embeddings-search.md)
- [Agentes con RAG](04-agents-with-rag.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
