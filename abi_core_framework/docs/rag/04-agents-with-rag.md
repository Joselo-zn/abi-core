# Agents with RAG

Build an agent that answers questions using your own documents.

```{note}
`store_document`/`search_documents` are **not** built-in — the Semantic Layer ships with agent and tool discovery only. Add the two tools first, as shown in [Extending the Semantic Layer](../semantic-layer/04-extending-semantic-layer.md). After that, the `MCPToolkit` calls below work as written: `MCPToolkit` calls whatever tool names the Semantic Layer registers.
```

## The pattern

1. Store documents in the Semantic Layer (via MCPToolkit)
2. When a question arrives, search for relevant documents
3. Pass the documents + question to the LLM
4. Return the grounded answer

## Implementation

Edit your agent's `steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from abi_core.common.semantic_tools import MCPToolkit


@agent.step(name="search_knowledge")
async def search_knowledge(question):
    """Search stored documents for relevant context."""
    toolkit = MCPToolkit()
    found = await toolkit.search_documents(query=question, max_results=3)
    docs = found if isinstance(found, list) else []  # a dict means {"error": ...}

    context = "\n".join(doc["content"] for doc in docs)
    return {"context": context, "sources": docs}


@agent.step(name="answer_with_context")
async def answer_with_context(question, context):
    """Answer using retrieved documents as context."""
    prompt = f"""Answer the following question using ONLY the provided context.
If the context doesn't contain the answer, say "I don't have that information."

Context:
{context}

Question: {question}

Answer:"""

    result = await invoke(config.LLM_CONFIG, prompt)
    return {"answer": result}
```

And your `tasks.py`:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="ask", task_id="task-ask")
async def ask(query):
    # "Index: <text>" stores a document; anything else is a question.
    if query.startswith("Index:"):
        stored = await agent.execute_step(
            "index_document", content=query[len("Index:"):].strip(), metadata={"source": "chat"}
        )
        yield AgentResponse.result(stored)
        return

    question = query

    yield AgentResponse.status("Searching knowledge base...")
    knowledge = await agent.execute_step("search_knowledge", question=question)

    if not knowledge["context"]:
        yield AgentResponse.result({"answer": "I don't have information about that."})
        return

    yield AgentResponse.status("Generating answer...")
    result = await agent.execute_step(
        "answer_with_context",
        question=question,
        context=knowledge["context"],
    )

    yield AgentResponse.result({
        "answer": result["answer"],
        "sources": knowledge["sources"],
    })
```

## Indexing documents

Add this step to `steps.py` — the task above calls it for every message that starts with `Index:`:

```python
@agent.step(name="index_document")
async def index_document(content, metadata):
    """Store a document in the Semantic Layer for RAG."""
    toolkit = MCPToolkit()
    result = await toolkit.store_document(content=content, metadata=metadata)
    return result
```

You can also call it from any other task or script to load documents in bulk:

```python
await agent.execute_step(
    "index_document",
    content="Our return policy allows 30 days for full refund with original packaging.",
    metadata={"type": "policy", "department": "support", "version": "2.1"},
)
```

## Test it

```bash
# Index a document
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Index: Our premium plan costs $49/month and includes unlimited agents."}'

# Ask about it
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "How much does the premium plan cost?"}'
# → "The premium plan costs $49/month and includes unlimited agents."
```

## Why this is better than stuffing everything in the prompt

- **Scales** — You can have thousands of documents. Only relevant ones are retrieved.
- **Fresh** — Add new documents anytime. No need to retrain or redeploy.
- **Grounded** — The LLM answers from your data, not from its training. Less hallucination.
- **Auditable** — You can see which sources were used for each answer.

## Next step

👉 [Guardian Service](../security/01-guardian-service.md)
