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
| `AgentCard` | Agent descriptions + capabilities (for discovery via `find_agent`/`recommend_agents`) |
| `MeshItem` | Semantic mesh entries backing agent discovery/recommendation |
| `ToolRegistry` | Tool descriptions + schemas (for `search_tool_registry`) |
| Custom | Your own documents — not built in; add a collection + MCP tool if you need general-purpose document RAG |

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

If you need to interact with Weaviate directly, the Semantic Layer uses the
`weaviate-client>=4.0.0` collections API, not the older `weaviate.Client(...)` v3 style:

```python
import weaviate

client = weaviate.connect_to_local(host="localhost", port=8081)

# Query objects
col = client.collections.get("AgentCard")
result = col.query.fetch_objects(limit=5)

client.close()
```

But for most use cases, use `MCPToolkit` instead — it handles auth and sessions for you.

## Next step

👉 [Embeddings & Search](03-embeddings-search.md)
