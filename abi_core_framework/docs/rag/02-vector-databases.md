# Vector Databases

A vector database stores text in a way that lets you search by meaning instead of exact keywords. "analyze revenue" finds "sales analysis" because they mean similar things.

## Weaviate in ABI-Core

ABI-Core uses Weaviate. It's included automatically when you add the Semantic Layer:

```bash
abi-core create project my-app --with-semantic-layer
# Weaviate runs on port 8080 (mapped to 8081 on host)
```

## What it stores

| Collection | Content |
|-----------|---------|
| AgentCards | Agent descriptions + capabilities (for discovery) |
| ToolRegistry | Tool descriptions + schemas (for tool search) |
| Custom | Your documents (if you extend the Semantic Layer) |

## How data gets in

At startup, the Semantic Layer:
1. Reads JSON files from `agent_cards/` and `tool_cards/`
2. Generates embeddings using `nomic-embed-text:v1.5` (via Ollama)
3. Upserts into Weaviate collections
4. Skips cards that are already stored (deduplication by URI)

## Check Weaviate

```bash
# Is it ready?
curl http://localhost:8081/v1/.well-known/ready

# What's stored?
curl http://localhost:8081/v1/objects?limit=5
```

## Direct access (advanced)

If you need to interact with Weaviate directly:

```python
import weaviate

client = weaviate.Client("http://localhost:8081")

# Query objects
result = client.query.get("AgentCards", ["text", "uri"]).with_limit(5).do()
```

But for most use cases, use `MCPToolkit` instead — it handles auth and sessions for you.

## Next step

👉 [Embeddings & Search](03-embeddings-search.md)
