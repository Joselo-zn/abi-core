# Agents with RAG

Build an agent that answers questions using your own documents.

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
    results = await toolkit.search_documents(query=question, max_results=3)

    if "error" in results:
        return {"context": "", "sources": []}

    # Combine relevant documents into context
    context = "\n".join(
        doc.get("content", "") for doc in results if isinstance(doc, dict)
    )
    return {"context": context, "sources": results}


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
import json
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="ask", task_id="task-ask")
async def ask(query):
    data = json.loads(query) if isinstance(query, str) else query
    question = data.get("text", "")

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

Create a step or script that stores your documents:

```python
@agent.step(name="index_document")
async def index_document(content, metadata):
    """Store a document in the Semantic Layer for RAG."""
    toolkit = MCPToolkit()
    result = await toolkit.store_document(content=content, metadata=metadata)
    return result
```

Call it to index your data:

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
