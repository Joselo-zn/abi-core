# Semantic Search

The Semantic Layer doesn't match keywords — it matches meaning.

## How it's different

**Keyword search:**
```
Query: "analyze sales"
Only finds agents with the exact words "analyze" AND "sales"
```

**Semantic search:**
```
Query: "examine revenue trends"
Finds the "sales analysis" agent because the meaning is similar
```

## Under the hood

1. Your query → embedding vector (via `nomic-embed-text`)
2. Agent cards → embedding vectors (generated at startup)
3. Cosine similarity → ranked results

The embedding model understands that "examine" ≈ "analyze" and "revenue" ≈ "sales".

## Tool cards too

The Semantic Layer also indexes tool cards. Search for tools by capability:

```python
from abi_core.common.semantic_tools import tool_search_tools

tools = await tool_search_tools.ainvoke("search documents by content")
# Returns matching tool cards with name, description, and access_scope
```

## What makes a good agent card for discovery

The more descriptive your card, the better the search works:

```json
{
  "description": "Analyzes financial data including revenue, expenses, and profit margins",
  "supportedTasks": ["analyze_revenue", "calculate_margins", "forecast_trends"],
  "skills": [
    {
      "description": "Analyzes quarterly revenue data and identifies growth patterns",
      "tags": ["finance", "revenue", "analysis", "trends", "quarterly"]
    }
  ]
}
```

Tips:
- Use natural language in `description` (not just keywords)
- Be specific in `supportedTasks`
- Add relevant `tags` to skills
- Include synonyms in descriptions ("revenue/sales", "analyze/examine")

## Next step

👉 [Extending the Semantic Layer](04-extending-semantic-layer.md)
