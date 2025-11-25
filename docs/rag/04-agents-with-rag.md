# Agentes con RAG

Crea agentes que usan RAG para responder con información específica.

## Agente RAG Básico

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
            description='Agente con RAG'
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
        
        # Buscar y generar respuesta
        response = self.qa_chain.invoke({"query": query})
        
        return {
            'result': response['result'],
            'query': query
        }
```

## Indexar Documentos

```python
# Agregar documentos a Weaviate
documentos = [
    "Producto A cuesta $99",
    "Producto B cuesta $149",
    "Envíos gratis en compras mayores a $50"
]

for doc in documentos:
    weaviate_client.data_object.create({
        "content": doc
    }, "Document")
```

## Usar el Agente

```bash
curl -X POST http://localhost:8000/stream \
  -d '{"query": "¿Cuánto cuesta el producto A?", "context_id": "test", "task_id": "1"}'
# Respuesta: "El producto A cuesta $99"
```

## Próximos Pasos

- [Seguridad y políticas](../security/01-guardian-service.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
