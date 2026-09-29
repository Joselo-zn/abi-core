# What is RAG?

RAG (Retrieval-Augmented Generation) = search your data first, then let the AI answer using what you found.

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
agent = await toolkit.find_agent(task_description="analyze quarterly revenue")
```

```{note}
There is no built-in general-purpose document store (no `store_document`/`search_documents`
MCP tool ships with the framework). To do RAG over your own documents, add a Weaviate
collection and a matching `@mcp.tool` to the Semantic Layer's `main.py` — the same pattern
already used there for `register_tool`/`search_tool_registry`. See
[Agents with RAG](04-agents-with-rag.md) for how that MCP tool would look once you've added it.
```

## When to use RAG

- You have documents, manuals, or knowledge bases
- You need answers grounded in your specific data
- You want to reduce LLM hallucinations

## Next step

👉 [Vector Databases](02-vector-databases.md)
