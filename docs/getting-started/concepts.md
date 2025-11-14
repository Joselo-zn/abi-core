# Core Concepts

Understanding the key concepts behind ABI-Core will help you build better agent systems.

## Agent-Based Infrastructure (ABI)

ABI is an architectural paradigm where intelligent agents collaborate through:

- **Semantic Context** - Shared understanding through vector embeddings
- **Policy-Driven Governance** - OPA-based security and access control
- **Modular Orchestration** - Flexible agent composition and communication

## Key Components

### 1. Agents

Agents are autonomous AI entities that:
- Process natural language queries
- Execute tasks using tools and functions
- Communicate with other agents via A2A protocol
- Maintain conversation context and memory

**Example Agent:**
```python
from abi_core.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='my-agent',
            description='A helpful AI assistant'
        )
    
    async def stream(self, query: str, context_id: str, task_id: str):
        # Process query and yield responses
        response = await self.llm.ainvoke(query)
        yield {
            'content': response.content,
            'response_type': 'text',
            'is_task_completed': True
        }
```

### 2. Semantic Layer

The semantic layer provides:
- **Agent Discovery** - Find agents by capability using MCP protocol
- **Vector Storage** - Weaviate-based semantic search
- **Agent Cards** - Structured metadata about agent capabilities
- **Context Management** - Shared knowledge across agents

### 3. A2A Protocol

Agent-to-Agent communication protocol enables:
- Direct agent-to-agent messaging
- Task delegation and orchestration
- Distributed workflows
- Event-driven interactions

### 4. Security & Governance

OPA-based security provides:
- Fine-grained access control
- Policy enforcement at runtime
- Audit logging
- Compliance validation

## LLM Models

### Default Model: qwen2.5:3b

ABI-Core uses **qwen2.5:3b** as the default model because:

✅ **Excellent Tool Calling** - Essential for agent function execution  
✅ **Compact Size** - ~2 GB download  
✅ **Fast Inference** - Quick response times  
✅ **Strong Reasoning** - Good instruction following  
✅ **Production Ready** - Stable and reliable  

### Supported Models

You can use any Ollama-compatible model:

```bash
# Larger models for better performance
ollama pull llama3.2:3b
ollama pull mistral:7b
ollama pull llama3.1:8b

# Smaller models for resource-constrained environments
ollama pull phi3:mini
ollama pull gemma2:2b
```

**Important:** Ensure your chosen model supports **function/tool calling** for agent workflows.

### Changing Models

Specify a different model when creating agents:

```bash
abi-core add agent my-agent --model mistral:7b
```

Or set it in your project configuration:

```yaml
# .abi/runtime.yaml
agents:
  my-agent:
    model: "mistral:7b"
```

## Model Serving Modes

### Centralized (Recommended for Production)

Single Ollama instance serves all agents:
- Lower resource usage
- Easier model management
- Faster agent startup

```bash
abi-core create project my-app --model-serving centralized
```

### Distributed (Default)

Each agent has its own Ollama instance:
- Complete isolation
- Independent model versions
- Development friendly

```bash
abi-core create project my-app --model-serving distributed
```

See [Model Serving Guide](../user-guide/model-serving.md) for details.

## Project Structure

```
my-project/
├── agents/              # Your AI agents
│   └── my-agent/
│       ├── main.py      # Entry point
│       ├── my_agent.py  # Agent implementation
│       └── agent_cards/ # Agent metadata
├── services/            # Supporting services
│   ├── semantic_layer/  # Agent discovery
│   └── guardian/        # Security policies
├── compose.yaml         # Docker orchestration
└── .abi/
    └── runtime.yaml     # Project configuration
```

## Configuration

### Runtime Configuration

`.abi/runtime.yaml` stores project settings:

```yaml
project:
  name: my-project
  domain: general
  model_serving: centralized

agents:
  my-agent:
    model: qwen2.5:3b
    port: 8000
```

### Environment Variables

Control behavior via environment variables:

```bash
MODEL_NAME=qwen2.5:3b
OLLAMA_HOST=http://localhost:11434
AGENT_PORT=8000
LOG_LEVEL=INFO
```

## Next Steps

- [Create your first project](../user-guide/creating-projects.md)
- [Build custom agents](../user-guide/agents.md)
- [Configure semantic layer](../user-guide/semantic-layer.md)
- [Deploy to production](../user-guide/deployment.md)
