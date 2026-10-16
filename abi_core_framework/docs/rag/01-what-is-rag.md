# What is RAG?

Ask a model about your return policy and it has two options: admit it doesn't know, or make one up. The second one sounds better. That's the problem.

RAG — Retrieval-Augmented Generation — takes the choice away: search your own data first, then let the model answer using only what you found. The model brings the language. Your documents bring the facts.

## The problem

AI models know general things but nothing about your company, your products, or your internal docs.

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

The Semantic Layer already uses RAG internally — agent cards and tool cards are stored as
embeddings in Weaviate (`AgentCard`/`MeshItem`/`ToolRegistry` collections) and searched
semantically for agent discovery (`find_agent`, `recommend_agents`) and tool lookup
(`search_tool_registry`):

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

results = await toolkit.search_tool_registry(query="parse a PDF")
agent = await toolkit.find_agent(query="analyze quarterly revenue")
```

```{note}
There is no built-in general-purpose document store. To do RAG over your own documents, add a `store_document`/`search_documents` pair of tools to the Semantic Layer — [Extending the Semantic Layer](../semantic-layer/04-extending-semantic-layer.md) shows a minimal version — then follow [Agents with RAG](04-agents-with-rag.md).
```

## When to use RAG

- You have documents, manuals, or knowledge bases
- You need answers grounded in your specific data
- You want to reduce LLM hallucinations

## Next step

👉 [Vector Databases](02-vector-databases.md)
