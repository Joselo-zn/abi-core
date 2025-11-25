# Agents with RAG

Create agents that use RAG to respond with specific information.

## Basic RAG Agent

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Weaviate
import weaviate

class RAGAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='rag-agent',
            description='Agent with RAG'
        )
        self.setup_rag()
    
    def setup_rag(self):
        # LLM
        self.llm = ChatOllama(model='qwen2.5:3b')
        
        # Weaviate
        weaviate_client = weaviate.Client("http://localhost:8080")
        vectorstore = Weaviate(weaviate_client, "Document", "content")
        
        # RAG Chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            retriever=vectorstore.as_retriever()
        )
    
    def process(self, enriched_input):
        query = enriched_input['query']
        
        # Search and generate response
        response = self.qa_chain.invoke({"query": query})
        
        return {
            'result': response['result'],
            'query': query
        }
```

## Index Documents

```python
# Add documents to Weaviate
documents = [
    "Product A costs $99",
    "Product B costs $149",
    "Free shipping on orders over $50"
]

for doc in documents:
    weaviate_client.data_object.create({
        "content": doc
    }, "Document")
```

## Use the Agent

```bash
curl -X POST http://localhost:8000/stream \
  -d '{"query": "How much does product A cost?", "context_id": "test", "task_id": "1"}'
# Response: "Product A costs $99"
```

## Next Steps

- [Security and policies](../security/01-guardian-service.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
