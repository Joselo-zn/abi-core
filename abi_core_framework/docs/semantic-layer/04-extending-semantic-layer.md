# Extending the Semantic Layer

Add your own MCP tools to the Semantic Layer so any agent can call them via `MCPToolkit`.

## Why extend it

The Semantic Layer is a shared service. If you add a tool there, every agent in your system can use it — store documents, query data, trigger workflows, anything.

## Add a custom MCP tool

In your semantic layer's MCP server (`services/semantic_layer/main.py`, a
[FastMCP](https://github.com/jlowin/fastmcp) app), register a new tool with
`@mcp.tool(...)` — the same decorator the built-in tools
(`find_agent`, `register_agent`, `search_tool_registry`, ...) use:

```python
# services/semantic_layer/main.py

import uuid

# A deliberately simple store: a dict in the Semantic Layer's process.
# Good enough to see the whole loop work. For real retrieval by meaning,
# back these two tools with a Weaviate collection of your own.
_DOCUMENTS: dict[str, dict] = {}


@mcp.tool(name='store_document', description='Store a document for later retrieval')
async def store_document(content: str, metadata: dict | None = None) -> dict:
    """Store a document for later retrieval."""
    doc_id = str(uuid.uuid4())
    _DOCUMENTS[doc_id] = {"doc_id": doc_id, "content": content, "metadata": metadata or {}}
    return {"success": True, "doc_id": doc_id}


@mcp.tool(name='search_documents', description='Find stored documents that mention the query words')
async def search_documents(query: str, max_results: int = 5) -> list:
    """Find stored documents that mention the query words."""
    words = {w.lower() for w in query.split()}
    scored = [
        (sum(w in doc["content"].lower() for w in words), doc)
        for doc in _DOCUMENTS.values()
    ]
    hits = [doc for score, doc in sorted(scored, key=lambda x: -x[0]) if score > 0]
    return hits[:max_results]
```

Add `@validate_semantic_access` (from
`abi_core.semantic.semantic_access_validator`) between `@mcp.tool(...)` and
`async def ...` if the tool should go through the same OPA-backed agent/user
check the built-in tools use — see [A2A Validation → Semantic Layer access
validation](../security/06-a2a-validation.md#semantic-layer-mcp-access-validation).

## Call it from any agent

```python
from abi_core.common.semantic_tools import MCPToolkit

toolkit = MCPToolkit()

# Store something
await toolkit.store_document(
    content="Q4 revenue was $2.3M, up 15% from Q3",
    metadata={"type": "financial", "quarter": "Q4"}
)

# Search later
found = await toolkit.search_documents(query="revenue growth")
for doc in found:
    print(doc["content"])
```

## Add tool cards for discovery

Create a JSON file in `services/semantic_layer/tool_cards/`:

```json
{
  "tool_name": "store_document",
  "description": "Stores documents for future semantic retrieval",
  "objective": "Persist information that agents can query later",
  "input_schema": {
    "content": "string - the document text",
    "metadata": "dict - optional metadata tags"
  },
  "output_schema": {
    "success": "boolean",
    "doc_id": "string"
  },
  "metadata": {
    "tags": ["storage", "documents", "memory", "persistence"]
  }
}
```

Now agents can discover this tool via `tool_search_tools`:

```python
tools = await tool_search_tools.ainvoke("store information for later")
# → Returns your store_document tool card
```

## Next step

👉 [MCPToolkit](05-mcp-toolkit.md)
