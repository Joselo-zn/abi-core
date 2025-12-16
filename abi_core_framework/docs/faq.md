# Frequently Asked Questions

## General

### What is ABI-Core?

ABI-Core is a framework for building Agent-Based Infrastructure systems. It provides tools for creating, deploying, and managing AI agents with semantic layers, orchestration, and security policies.

### Is ABI-Core production-ready?

ABI-Core v1.2.0 is production-ready with a stable API. The framework includes comprehensive security, modular architecture, and enhanced web interfaces for seamless integration.

### What license is ABI-Core under?

Apache 2.0 License. See [LICENSE](https://github.com/Joselo-zn/abi-core/blob/main/LICENSE) for details.

## Installation & Setup

### What are the system requirements?

- Python 3.11 or higher
- Docker and Docker Compose
- Ollama for LLM serving
- 8 GB RAM minimum (16 GB recommended)
- 10 GB disk space for models

### Do I need a GPU?

No, ABI-Core works on CPU-only systems. However, GPU acceleration significantly improves inference speed.

### Can I use cloud-hosted LLMs instead of Ollama?

Currently, ABI-Core is designed for Ollama. Support for cloud LLMs (OpenAI, Anthropic, etc.) is planned for future releases.

## Models

### How do I download models?

Use the automated provision-models command:

```bash
cd my-project
abi-core provision-models
```

This automatically:
- Starts required services (Ollama or agents)
- Downloads LLM and embedding models
- Updates runtime.yaml with status

### What does provision-models do?

The `provision-models` command:
1. Detects your project's model serving mode (centralized/distributed)
2. Starts necessary Docker services automatically
3. Downloads the LLM model (qwen2.5:3b by default)
4. Downloads the embedding model (nomic-embed-text:v1.5)
5. Updates `.abi/runtime.yaml` with provisioning status
6. Skips already downloaded models (idempotent)

### Do I need to start services before provision-models?

No! The command automatically starts required services:
- **Centralized mode**: Starts main Ollama service
- **Distributed mode**: Starts all agent services (with their Ollama instances)

### Why qwen2.5:3b as default?

qwen2.5:3b offers the best balance of:
- Excellent tool/function calling support (critical for agents)
- Reasonable size (~2 GB)
- Fast inference
- Strong reasoning capabilities

### Can I use a different model?

Yes! Specify any Ollama-compatible model:

```bash
abi-core add agent my-agent --model mistral:7b
```

**Important:** Ensure the model supports function/tool calling.

### Which models support tool calling?

Recommended models with tool support:
- ✅ qwen2.5:3b (excellent)
- ✅ mistral:7b (excellent)
- ✅ llama3.1:8b (very good)
- ✅ phi3:mini (good)
- ⚠️ gemma2:2b (basic)

### How do I know if a model supports tools?

Test it:

```bash
ollama show <model-name>
```

Look for "tools" or "function calling" in the capabilities.

### Can I use different models for different agents?

Yes! Each agent can use a different model:

```bash
abi-core add agent researcher --model qwen2.5:3b
abi-core add agent writer --model mistral:7b
```

## Architecture

### What's new in v1.2.0?

**Modular Architecture:**
- Reorganized into 5 focused packages: abi-core, abi-agents, abi-services, abi-cli, abi-framework
- Maintains full backward compatibility with existing imports
- Easier community contributions and independent package development

**Enhanced Open WebUI Compatibility:**
- Fixed `Unclosed client session` errors in streaming responses
- Improved connection management and proper headers
- Better real-time response handling for web interfaces

### What's the difference between centralized and distributed model serving?

**Centralized:**
- Single Ollama instance serves all agents
- Lower resource usage
- Easier management
- Recommended for production

**Distributed:**
- Each agent has its own Ollama instance
- Complete isolation
- Higher resource usage
- Better for development

See [Model Serving Guide](user-guide/model-serving.md) for details.

### How do agents communicate?

Agents use the A2A (Agent-to-Agent) protocol, which is built on top of HTTP/SSE for real-time streaming communication.

### What is the Semantic Layer?

The Semantic Layer provides:
- Agent discovery via MCP protocol
- Vector-based semantic search (Weaviate)
- Agent capability metadata (Agent Cards)
- Shared context across agents

## Development

### How do I create a custom agent?

```bash
# Create project
abi-core create project my-project

# Add agent
abi-core add agent my-agent --description "My custom agent"

# Edit agents/my-agent/my_agent.py
# Implement your agent logic
```

See [Creating Agents](user-guide/agents.md) for details.

### Can I use LangChain tools?

Yes! ABI-Core agents are built on LangChain, so you can use any LangChain tool:

```python
from langchain.tools import DuckDuckGoSearchRun

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(agent_name='my-agent')
        self.tools = [DuckDuckGoSearchRun()]
```

### How do I add custom tools?

Define tools in your agent:

```python
from langchain.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """My custom tool description"""
    return f"Processed: {query}"

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(agent_name='my-agent')
        self.tools = [my_custom_tool]
```

## Deployment

### How do I deploy to production?

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

See [Deployment Guide](user-guide/deployment.md) for production best practices.

### Can I deploy to Kubernetes?

Yes! ABI-Core generates Docker images that can be deployed to Kubernetes. K8s manifests generation is planned for future releases.

### How do I scale agents?

With centralized model serving:

```bash
docker-compose up --scale my-agent=3
```

This creates 3 instances of the agent sharing the same Ollama service.

## Troubleshooting

### Agent returns "model not found" error

Pull the model first:

```bash
docker exec <container-name> ollama pull qwen2.5:3b
```

Or for centralized Ollama:

```bash
docker exec myproject-ollama ollama pull qwen2.5:3b
```

### Port already in use

Change the port in `.abi/runtime.yaml`:

```yaml
agents:
  my-agent:
    port: 8001  # Change from 8000
```

### Out of memory errors

Use a smaller model:

```bash
abi-core add agent my-agent --model phi3:mini
```

Or increase Docker memory limit:

```bash
docker-compose up --memory=8g
```

### Agent not responding

Check logs:

```bash
docker-compose logs my-agent
```

Common issues:
- Model not loaded
- Ollama not running
- Port conflicts

### Tool calling not working

Verify your model supports tools:

```bash
ollama show qwen2.5:3b
```

If not, switch to a model with tool support:

```bash
abi-core add agent my-agent --model mistral:7b
```

## Performance

### How can I make agents faster?

1. **Use GPU acceleration** (if available)
2. **Use smaller models** (phi3:mini, gemma2:2b)
3. **Enable centralized model serving**
4. **Reduce context window size**
5. **Limit concurrent requests**

See [Performance Guide](architecture/performance.md) for details.

### How much RAM do I need?

Minimum requirements by model:
- qwen2.5:3b: 4 GB
- mistral:7b: 8 GB
- llama3.1:8b: 8 GB
- phi3:mini: 4 GB
- gemma2:2b: 3 GB

Add 2-4 GB for system overhead.

### Can I run multiple agents on one machine?

Yes! Use centralized model serving to share resources:

```bash
abi-core create project my-app --model-serving centralized
abi-core add agent agent1
abi-core add agent agent2
abi-core add agent agent3
```

All agents share one Ollama instance.

## Security

### How do I secure my agents?

ABI-Core includes OPA-based security:

```bash
abi-core add service guardian
```

This adds policy enforcement, access control, and audit logging.

### Can I use authentication?

Yes! Add authentication middleware to your agents. JWT and API key authentication examples are in the documentation.

### Are agent communications encrypted?

By default, agents communicate over HTTP. For production, configure HTTPS/TLS in your reverse proxy (nginx, traefik, etc.).

## Community

### How do I report bugs?

Open an issue on [GitHub Issues](https://github.com/Joselo-zn/abi-core/issues).

### How do I contribute?

See [Contributing Guide](development/contributing.md) for details.

### Where can I get help?

- [GitHub Discussions](https://github.com/Joselo-zn/abi-core/discussions)
- [Documentation](https://abi-core.readthedocs.io)
- Email: jl.mrtz@gmail.com

## Roadmap

### What's coming next?

See [Roadmap](roadmap.md) for planned features:
- Enhanced orchestration (v0.2.0)
- Advanced semantic search (v0.3.0)
- Multi-cloud deployment (v0.4.0)
- Stable v1.0.0 (Q3 2026)

### Can I request features?

Yes! Open a feature request on [GitHub Issues](https://github.com/Joselo-zn/abi-core/issues) with the "enhancement" label.
