# LLM Models Guide

Complete guide for choosing, configuring, and provisioning LLM models in ABI-Core.

## Automated Model Provisioning

ABI-Core provides the `provision-models` command to automatically download and configure models:

```bash
# Navigate to your project
cd my-project

# Provision models (auto-starts services and downloads models)
abi-core provision-models
```

### What provision-models Does

1. **Starts required services** automatically (Ollama or agents)
2. **Downloads LLM model** (qwen2.5:3b by default)
3. **Downloads embedding model** (nomic-embed-text:v1.5)
4. **Updates runtime.yaml** with provisioning status
5. **Idempotent** - skips already downloaded models

### Behavior by Mode

**Centralized Mode:**
- Starts main Ollama service
- Downloads models to centralized Ollama
- All agents share the same models

**Distributed Mode:**
- Starts each agent (with their own Ollama)
- Downloads LLM to each agent's Ollama
- Starts main Ollama for embeddings
- Downloads embeddings to main Ollama

## Default Model: qwen2.5:3b

ABI-Core uses **qwen2.5:3b** as the default model for all agents.

### Why qwen2.5:3b?

| Feature | Rating | Notes |
|---------|--------|-------|
| **Tool Calling** | ⭐⭐⭐⭐⭐ | Excellent function/tool support |
| **Size** | ⭐⭐⭐⭐ | ~2 GB (reasonable) |
| **Speed** | ⭐⭐⭐⭐⭐ | Fast inference |
| **Reasoning** | ⭐⭐⭐⭐ | Strong instruction following |
| **Memory** | ⭐⭐⭐⭐ | ~4 GB RAM required |

### Automatic Installation

```bash
# Automatically installed with provision-models
abi-core provision-models
```

### Manual Installation

```bash
ollama pull qwen2.5:3b
```

## Recommended Models

### For Production

#### qwen2.5:3b (Default)
```bash
ollama pull qwen2.5:3b
```
- **Best for:** General agent workflows
- **Size:** ~2 GB
- **RAM:** ~4 GB
- **Tool calling:** Excellent

#### mistral:7b
```bash
ollama pull mistral:7b
```
- **Best for:** Complex reasoning tasks
- **Size:** ~4.1 GB
- **RAM:** ~8 GB
- **Tool calling:** Excellent

#### llama3.1:8b
```bash
ollama pull llama3.1:8b
```
- **Best for:** High-quality responses
- **Size:** ~4.7 GB
- **RAM:** ~8 GB
- **Tool calling:** Very good

### For Development

#### phi3:mini
```bash
ollama pull phi3:mini
```
- **Best for:** Quick testing
- **Size:** ~2.3 GB
- **RAM:** ~4 GB
- **Tool calling:** Good

#### gemma2:2b
```bash
ollama pull gemma2:2b
```
- **Best for:** Resource-constrained environments
- **Size:** ~1.6 GB
- **RAM:** ~3 GB
- **Tool calling:** Basic

## Model Requirements

### Critical: Tool Calling Support

**All agent models MUST support function/tool calling.**

Agents rely on tools to:
- Execute actions
- Query databases
- Call external APIs
- Interact with other agents

### Verify Tool Support

Test if a model supports tools:

```bash
# Pull the model
ollama pull <model-name>

# Test with a simple tool call
curl http://localhost:11434/api/generate -d '{
  "model": "<model-name>",
  "prompt": "Use the calculator tool to compute 2+2",
  "tools": [{"name": "calculator", "description": "Performs calculations"}]
}'
```

## Changing Models

### Per Agent

Specify model when creating an agent:

```bash
abi-core add agent my-agent --model mistral:7b
```

### Per Project

Set default in `.abi/runtime.yaml`:

```yaml
project:
  default_model: mistral:7b

agents:
  agent1:
    model: qwen2.5:3b  # Override for specific agent
  agent2:
    model: mistral:7b
```

### Via Environment Variable

```bash
export MODEL_NAME=mistral:7b
docker-compose up
```

## Model Comparison

| Model | Size | RAM | Speed | Tool Calling | Best For |
|-------|------|-----|-------|--------------|----------|
| **qwen2.5:3b** | 2 GB | 4 GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | General agents |
| **mistral:7b** | 4.1 GB | 8 GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | Complex reasoning |
| **llama3.1:8b** | 4.7 GB | 8 GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | High quality |
| **phi3:mini** | 2.3 GB | 4 GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | Development |
| **gemma2:2b** | 1.6 GB | 3 GB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Limited resources |

## Embedding Models

For semantic layer, use:

### nomic-embed-text:v1.5 (Default)
```bash
ollama pull nomic-embed-text:v1.5
```
- **Size:** ~274 MB
- **Dimensions:** 768
- **Best for:** General semantic search

### all-minilm:l6-v2
```bash
ollama pull all-minilm:l6-v2
```
- **Size:** ~23 MB
- **Dimensions:** 384
- **Best for:** Fast embeddings

## Performance Tuning

### GPU Acceleration

If you have a GPU:

```yaml
# compose.yaml
services:
  my-project-ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### CPU Optimization

For CPU-only systems:

```bash
# Use smaller models
export MODEL_NAME=phi3:mini

# Limit concurrent requests
export OLLAMA_NUM_PARALLEL=2
```

### Memory Management

```bash
# Reduce context window
export OLLAMA_MAX_LOADED_MODELS=1

# Unload models after use
export OLLAMA_KEEP_ALIVE=5m
```

## Troubleshooting

### Model Not Found

```bash
# Pull the model first
ollama pull qwen2.5:3b

# Verify it's available
ollama list
```

### Out of Memory

```bash
# Use a smaller model
abi-core add agent my-agent --model phi3:mini

# Or increase Docker memory limit
docker-compose up --memory=8g
```

### Slow Inference

```bash
# Use a smaller model
export MODEL_NAME=gemma2:2b

# Or enable GPU acceleration
# See GPU Acceleration section above
```

### Tool Calling Not Working

```bash
# Verify model supports tools
ollama show qwen2.5:3b

# Use a model with better tool support
abi-core add agent my-agent --model mistral:7b
```

## Provision Models Command Reference

### Basic Usage

```bash
# Provision models with default settings
abi-core provision-models

# Force re-download even if models exist
abi-core provision-models --force
```

### Output Example

**Centralized Mode:**
```
🚀 my-project Model Provisioner
Mode: centralized
LLM: qwen2.5:3b
Embeddings: nomic-embed-text:v1.5
========================================

📦 CENTRALIZED MODE
-------------------
[14:30:15] 🚀 Starting service: my-project-ollama...
[14:30:18] ✅ Service my-project-ollama started
[14:30:21] 🚦 Waiting for Ollama in my-project-ollama...
[14:30:23] ✅ Ollama ready in my-project-ollama
[14:30:23] ⬇️  Pulling 'qwen2.5:3b' in my-project-ollama...
[14:32:50] ✅ Model 'qwen2.5:3b' ready in my-project-ollama
[14:32:50] ⬇️  Pulling 'nomic-embed-text:v1.5' in my-project-ollama...
[14:33:17] ✅ Model 'nomic-embed-text:v1.5' ready in my-project-ollama

========================================
🎉 Model provisioning completed!
========================================
LLM: qwen2.5:3b ✅
Embeddings: nomic-embed-text:v1.5 ✅

✅ Models provisioned successfully!
📝 Updated runtime.yaml with provisioning status
```

**Distributed Mode:**
```
🚀 my-project Model Provisioner
Mode: distributed
LLM: qwen2.5:3b
Embeddings: nomic-embed-text:v1.5
========================================

📦 DISTRIBUTED MODE
-------------------

Agent: agent1
[14:30:15] 🚀 Starting service: my-project-agent1...
[14:30:18] ✅ Service my-project-agent1 started
[14:30:21] 🚦 Waiting for Ollama in agent1...
[14:30:35] ✅ Ollama ready in agent1
[14:30:35] ⬇️  Pulling 'qwen2.5:3b' in agent1...
[14:33:02] ✅ Model 'qwen2.5:3b' ready in agent1

Agent: agent2
[14:33:02] 🚀 Starting service: my-project-agent2...
[14:33:05] ✅ Service my-project-agent2 started
[14:33:08] 🚦 Waiting for Ollama in agent2...
[14:33:22] ✅ Ollama ready in agent2
[14:33:22] ⬇️  Pulling 'qwen2.5:3b' in agent2...
[14:35:49] ✅ Model 'qwen2.5:3b' ready in agent2

[14:35:49] 🚀 Starting service: my-project-ollama...
[14:35:52] ✅ Service my-project-ollama started

Embeddings (main ollama service):
[14:35:55] 🚦 Waiting for Ollama in my-project-ollama...
[14:35:57] ✅ Ollama ready in my-project-ollama
[14:35:57] ⬇️  Pulling 'nomic-embed-text:v1.5' in my-project-ollama...
[14:36:24] ✅ Model 'nomic-embed-text:v1.5' ready in my-project-ollama

========================================
🎉 Model provisioning completed!
========================================
LLM: qwen2.5:3b ✅
Embeddings: nomic-embed-text:v1.5 ✅
```

### Configuration

Models are configured in `.abi/runtime.yaml`:

```yaml
project:
  name: "my-project"
  model_serving: "centralized"
  default_model: "qwen2.5:3b"

models:
  llm:
    name: "qwen2.5:3b"
    provisioned: true  # Updated by provision-models
  embedding:
    name: "nomic-embed-text:v1.5"
    provisioned: true  # Updated by provision-models
```

### Environment Variables

You can customize timeouts:

```bash
# Set custom timeout (default: 900 seconds = 15 minutes)
TIMEOUT_SECS=1800 abi-core provision-models

# Set custom polling interval (default: 10 seconds)
PULL_POLL_SECS=5 abi-core provision-models

# Set custom ready wait (default: 2 seconds)
READY_WAIT_SECS=1 abi-core provision-models
```

## Best Practices

1. **Use provision-models** - Automated and reliable model setup
2. **Start with qwen2.5:3b** - Good balance of performance and resources
3. **Test locally first** - Verify model works before deploying
4. **Monitor resource usage** - Adjust model size based on available resources
5. **Use GPU when available** - Significantly faster inference
6. **Keep models updated** - Re-run provision-models to update

```bash
# Update all models
abi-core provision-models --force
```

## Next Steps

- [Model Serving Guide](../MODEL_SERVING_GUIDE.md) - Centralized vs Distributed
- [Quick Start](../getting-started/quickstart.md) - Get started quickly
- [Deployment Guide](deployment.md) - Production setup
