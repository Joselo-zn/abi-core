# Embeddings & Search

Embeddings turn text into numbers. Similar text → similar numbers → found by search.

## How embeddings work

```
"analyze revenue data"  → [0.82, 0.15, 0.91, ...]
"examine sales figures" → [0.79, 0.18, 0.88, ...]  ← similar!
"cook a pizza"          → [0.12, 0.95, 0.03, ...]  ← very different
```

When you search for "analyze revenue", the database finds documents with similar vectors — even if they use different words.

## The embedding model

ABI-Core uses `nomic-embed-text:v1.5` running on Ollama. It's pulled automatically during setup:

```bash
docker exec <ollama-container> ollama pull nomic-embed-text:v1.5
```

The Semantic Layer's embedding mesh uses it to:
- Embed agent card descriptions at startup
- Embed tool card descriptions at startup
- Embed search queries at runtime

## Search in practice

When you call `tool_find_agent("analyze revenue")`:

1. Your query is embedded → `[0.82, 0.15, 0.91, ...]`
2. Weaviate compares against all stored agent card embeddings
3. Returns the closest match (cosine similarity)
4. That's your agent

Same for `tool_search_tools("store documents")` — searches tool card embeddings.

## Make your cards searchable

The more descriptive your text, the better the search:

```json
{
  "description": "Analyzes financial data including quarterly revenue, profit margins, and growth trends",
  "skills": [
    {
      "description": "Performs deep analysis of revenue patterns across time periods",
      "tags": ["finance", "revenue", "analysis", "quarterly", "trends"]
    }
  ]
}
```

The embedding is generated from the combined text of description + skills + tags.

## Next step

👉 [Agents with RAG](04-agents-with-rag.md)
