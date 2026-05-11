# What is RAG?

RAG (Retrieval-Augmented Generation) = search your data first, then let the LLM answer using what you found.

## The problem

LLMs know general things but nothing about your company, your products, or your internal docs.

```
User: "What's the return policy?"
LLM without RAG: "I don't have that information."
LLM with RAG: "You have 30 days to return items. See policy doc #42."
```

## How it works

```
User question
  → Convert to embedding (vector)
  → Search Weaviate for similar documents
  → Pass documents + question to LLM
  → LLM generates answer using your data
```

## In ABI-Core

The Semantic Layer already uses RAG internally — agent cards and tool cards are stored as embeddings in Weaviate and searched semantically. You can extend this to store your own documents.

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Store a document
await toolkit.store_document(
    content="Return policy: 30 days, original packaging required.",
    metadata={"type": "policy", "department": "support"}
)

# Search later
results = await toolkit.search_documents(query="return policy")
```

## When to use RAG

- You have documents, manuals, or knowledge bases
- You need answers grounded in your specific data
- You want to reduce LLM hallucinations

## Next step

👉 [Vector Databases](02-vector-databases.md)
