# What is RAG?

RAG (Retrieval-Augmented Generation) allows agents to access specific information from your domain.

## The Problem

LLMs have general knowledge but don't know about:
- Your specific products
- Your internal documents
- Updated information

## The Solution: RAG

RAG = Retrieve relevant information + Generate response

```
User: "What's the price of product X?"
  ↓
1. Search in database → "Product X: $99"
2. LLM generates response → "Product X costs $99"
```

## RAG Components

### 1. Vector Database
Stores documents as vectors (Weaviate in ABI-Core).

### 2. Embeddings
Converts text to numerical vectors.

### 3. Semantic Search
Finds relevant documents.

### 4. LLM
Generates response using found documents.

## RAG Flow

```
User question
  ↓
Convert to embedding
  ↓
Search similar documents
  ↓
Pass documents + question to LLM
  ↓
Generated response
```

## When to Use RAG

✅ Use RAG when:
- You need domain-specific information
- You have documents/manuals/policies
- You want answers based on your data

❌ Don't use RAG when:
- You only need general knowledge
- You don't have documents to index

## Next Steps

- [Vector databases](02-vector-databases.md)
- [Embeddings and search](03-embeddings-search.md)
- [Agents with RAG](04-agents-with-rag.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
