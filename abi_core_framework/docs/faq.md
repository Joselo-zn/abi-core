# FAQ

## General

**What is ABI-Core?**
A Python framework for building AI agents that run as Docker containers, discover each other semantically, communicate via A2A protocol, and operate under policy-driven security.

**Is it production-ready?**
The pipeline works end-to-end. APIs may change between minor versions. Use it, but pin your version.

**What license?**
Apache 2.0.

## Setup

**Do I need a GPU?**
No. Works on CPU. GPU makes inference faster but isn't required.

**How much RAM?**
4 GB minimum for `qwen2.5:3b`. 8 GB recommended if running multiple agents + Weaviate.

**Can I use cloud LLMs instead of Ollama?**
Yes. Set `LLM_CONFIG` to `{"provider": "openai", "model": "gpt-4o", "api_key": "..."}`. Supports OpenAI, Gemini, Grok, Anthropic, Bedrock, Azure, Vertex.

## Models

**Why qwen2.5:3b as default?**
Good tool-calling support, small size (~2 GB), fast inference. Best balance for agent workloads.

**Can different agents use different models?**
Yes. Each agent has its own `LLM_CONFIG` in `config/config.py`. One can use Ollama, another OpenAI.

**Which models support tool calling?**
- qwen2.5:3b ✅ (excellent)
- mistral:7b ✅
- llama3.1:8b ✅
- qwen3:8b ✅

## Architecture

**How do agents find each other?**
Via the Semantic Layer. Agent cards are stored as embeddings in Weaviate. Agents search by describing what they need.

**How do agents talk to each other?**
A2A protocol — JSON-RPC over HTTP with streaming. Use `agent_connection()` from `abi_core.common.abi_a2a`.

**What's the difference between step, task, and tool?**
- `@agent.step` — deterministic DAG node, runs in fixed order
- `@agent.task` — orchestrates steps programmatically, supports streaming
- `@agent.tool` — like a step, but the LLM can also invoke it

## Troubleshooting

**"Model not found"**
```bash
docker exec <ollama-container> ollama pull qwen2.5:3b
```

**"Port already in use"**
Change the port in `compose.yaml` or stop the conflicting process.

**Agent not responding**
```bash
docker compose logs <agent-name>
```

Check if Ollama is running and the model is pulled.

**Semantic Layer not finding agents**
Verify agent card JSON files exist in `services/semantic_layer/agent_cards/` and restart the semantic layer.

## Community

- **Bugs**: [GitHub Issues](https://github.com/Joselo-zn/abi-core/issues)
- **Questions**: [GitHub Discussions](https://github.com/Joselo-zn/abi-core/discussions)
- **Examples**: [abi-core-examples](https://github.com/Joselo-zn/abi-core-examples)
