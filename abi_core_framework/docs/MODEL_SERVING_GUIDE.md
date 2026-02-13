# Model Serving Guide

Complete guide for choosing and configuring model serving strategies in ABI-Core.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Centralized Mode](#centralized-mode)
- [Distributed Mode](#distributed-mode)
- [Comparison](#comparison)
- [Use Cases](#use-cases)
- [Migration Guide](#migration-guide)
- [Troubleshooting](#troubleshooting)

---

## Overview

ABI-Core supports two model serving strategies for Ollama:

1. **Centralized** — Single shared Ollama service for all agents
2. **Distributed** — Each agent has its own Ollama instance

The choice affects resource usage, isolation, and management complexity.

---

## Centralized Mode

### Description

A single Ollama service serves all agents in the project. All agents connect to the same Ollama instance.

### Architecture

```
┌─────────────────────────────────────────┐
│         Centralized Ollama              │
│         (Port 11434)                    │
│                                         │
│  Models: qwen2.5:3b, nomic-embed, ...  │
└─────────────────────────────────────────┘
           ▲         ▲         ▲
           │         │         │
    ┌──────┴───┐ ┌──┴─────┐ ┌─┴────────┐
    │ Agent 1  │ │ Agent 2│ │ Agent 3  │
    │ (8000)   │ │ (8001) │ │ (8002)   │
    └──────────┘ └────────┘ └──────────┘
```

### Creating a Centralized Project

```bash
abi-core create project my-app \
  --domain general \
  --model-serving centralized \
  --with-semantic-layer
```

### Generated Docker Compose Structure

```yaml
services:
  # Centralized Ollama Service
  my-app-ollama:
    image: ollama/ollama:latest
    container_name: my-app-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    networks:
      - my-app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Agent using centralized Ollama
  trader-agent:
    build: ./agents/trader
    ports:
      - "8000:8000"  # Only agent port
    environment:
      - OLLAMA_HOST=http://my-app-ollama:11434  # Points to shared service
      - START_OLLAMA=false  # Don't start own Ollama
      - LOAD_MODELS=false
    depends_on:
      - my-app-ollama
    networks:
      - my-app-network

volumes:
  ollama_data:  # Shared volume
    driver: local
```

### Adding Agents in Centralized Mode

```bash
# All agents automatically use the centralized Ollama
abi-core add agent trader --description "Trading agent"
abi-core add agent analyst --description "Market analyst"
abi-core add agent risk --description "Risk assessment"
```

**Result:**
- 3 agents created
- All use `my-app-ollama:11434`
- No individual Ollama instances
- Shared model cache

### Advantages

✅ **Lower Resource Usage**
- Single Ollama process
- Shared model cache
- Reduced memory footprint

✅ **Easier Model Management**
- Update models in one place
- Consistent model versions across agents
- Centralized model downloads

✅ **Faster Agent Startup**
- Agents don't wait for Ollama to start
- No model loading per agent
- Quicker scaling

✅ **Production Ready**
- Simpler deployment
- Easier monitoring
- Better resource utilization

### Disadvantages

⚠️ **Shared Resource**
- All agents compete for Ollama resources
- Single point of failure
- Potential bottleneck under high load

⚠️ **Less Isolation**
- Agents share the same Ollama instance
- Can't use different Ollama versions
- Model conflicts possible

---

## Distributed Mode

### Description

Each agent has its own Ollama instance. Complete isolation between agents.

### Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Agent 1    │  │   Agent 2    │  │   Agent 3    │
│   (8000)     │  │   (8001)     │  │   (8002)     │
│              │  │              │  │              │
│   Ollama     │  │   Ollama     │  │   Ollama     │
│   (11434)    │  │   (11435)    │  │   (11436)    │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Creating a Distributed Project

```bash
abi-core create project my-app \
  --domain general \
  --model-serving distributed
# or simply (distributed is default)
abi-core create project my-app
```

### Generated Docker Compose Structure

```yaml
services:
  # Agent with own Ollama
  trader-agent:
    build: ./agents/trader
    ports:
      - "8000:8000"   # Agent port
      - "11434:11434" # Own Ollama port
    environment:
      - OLLAMA_HOST=http://localhost:11434
      - START_OLLAMA=true   # Start own Ollama
      - LOAD_MODELS=true
    volumes:
      - ollama_data:/root/.ollama  # Own volume
    networks:
      - my-app-network

  # Another agent with own Ollama
  analyst-agent:
    build: ./agents/analyst
    ports:
      - "8001:8001"   # Agent port
      - "11435:11434" # Own Ollama port (dynamic)
    environment:
      - OLLAMA_HOST=http://localhost:11435
      - START_OLLAMA=true
      - LOAD_MODELS=true
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - my-app-network
```

### Adding Agents in Distributed Mode

```bash
# Each agent gets its own Ollama instance
abi-core add agent trader --description "Trading agent"
abi-core add agent analyst --description "Market analyst"
```

**Result:**
- 2 agents created
- Each has own Ollama (ports 11434, 11435)
- Complete isolation
- Independent model management

### Advantages

✅ **Complete Isolation**
- Each agent has independent Ollama
- No resource competition
- Isolated failures

✅ **Independent Versions**
- Different Ollama versions per agent
- Different model versions
- Flexible configuration

✅ **Development Friendly**
- Easy to test different configurations
- No conflicts between agents
- Independent debugging

### Disadvantages

⚠️ **Higher Resource Usage**
- Multiple Ollama processes
- Duplicate model storage
- Higher memory consumption

⚠️ **Slower Startup**
- Each agent starts its own Ollama
- Model loading per agent
- Longer initialization time

⚠️ **More Complex Management**
- Update models per agent
- Monitor multiple Ollama instances
- Port management required

---

## Comparison

| Feature | Centralized | Distributed |
|---------|-------------|-------------|
| **Ollama Instances** | 1 shared | 1 per agent |
| **Resource Usage** | Low | High |
| **Memory Footprint** | ~2-4 GB | ~2-4 GB × agents |
| **Model Storage** | Shared | Duplicated |
| **Agent Startup** | Fast (~5s) | Slow (~30s) |
| **Isolation** | Shared | Complete |
| **Model Versions** | Unified | Independent |
| **Failure Impact** | All agents | Single agent |
| **Port Management** | Simple | Complex |
| **Recommended For** | Production | Development |
| **Scaling** | Easier | Harder |
| **Monitoring** | Centralized | Distributed |

---

## Use Cases

### When to Use Centralized

✅ **Production Deployments**
- Multiple agents in production
- Resource optimization needed
- Consistent model versions required

✅ **High Agent Count**
- 5+ agents in the same project
- Limited resources
- Shared infrastructure

✅ **Stable Environments**
- Well-tested configurations
- Minimal changes
- Predictable workloads

### When to Use Distributed

✅ **Development & Testing**
- Experimenting with different models
- Testing agent configurations
- Debugging individual agents

✅ **Low Agent Count**
- 1-3 agents
- Sufficient resources
- Independent development

✅ **Isolation Requirements**
- Different model versions needed
- Independent failure domains
- Separate testing environments

---

## Migration Guide

### From Distributed to Centralized

1. **Update runtime.yaml**
   ```yaml
   project:
     model_serving: "centralized"
   ```

2. **Add centralized Ollama service to compose.yaml**
   ```yaml
   services:
     myproject-ollama:
       image: ollama/ollama:latest
       ports:
         - "11434:11434"
       volumes:
         - ollama_data:/root/.ollama
       networks:
         - myproject-network
   ```

3. **Update each agent service**
   - Remove Ollama port (e.g., `11435:11434`)
   - Change `OLLAMA_HOST` to `http://myproject-ollama:11434`
   - Set `START_OLLAMA=false`
   - Set `LOAD_MODELS=false`
   - Add `depends_on: [myproject-ollama]`
   - Remove individual `ollama_data` volume

4. **Restart services**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### From Centralized to Distributed

1. **Update runtime.yaml**
   ```yaml
   project:
     model_serving: "distributed"
   ```

2. **Remove centralized Ollama service from compose.yaml**

3. **Update each agent service**
   - Add Ollama port (e.g., `11434:11434`, `11435:11434`)
   - Change `OLLAMA_HOST` to `http://localhost:PORT`
   - Set `START_OLLAMA=true`
   - Set `LOAD_MODELS=true`
   - Add `ollama_data:/root/.ollama` volume
   - Remove `depends_on` to Ollama service

4. **Restart services**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

---

## Troubleshooting

### Centralized Mode Issues

**Problem:** Agents can't connect to Ollama
```
Error: Connection refused to http://myproject-ollama:11434
```

**Solution:**
1. Check Ollama service is running:
   ```bash
   docker-compose ps myproject-ollama
   ```
2. Check healthcheck:
   ```bash
   docker-compose logs myproject-ollama
   ```
3. Verify network connectivity:
   ```bash
   docker-compose exec agent-name curl http://myproject-ollama:11434/api/tags
   ```

**Problem:** Models not found
```
Error: Model 'qwen2.5:3b' not found
```

**Solution:**
Pull models in centralized Ollama:
```bash
docker-compose exec myproject-ollama ollama pull qwen2.5:3b
docker-compose exec myproject-ollama ollama pull nomic-embed-text:v1.5
```

### Distributed Mode Issues

**Problem:** Port conflicts
```
Error: Port 11434 already in use
```

**Solution:**
ABI-Core automatically assigns dynamic ports (11434, 11435, 11436...). If conflicts persist:
1. Check used ports:
   ```bash
   docker-compose ps
   ```
2. Manually adjust ports in compose.yaml

**Problem:** High memory usage
```
System running out of memory
```

**Solution:**
1. Reduce number of agents
2. Switch to centralized mode
3. Increase system resources

---

## Best Practices

### Centralized Mode

1. **Monitor Ollama Performance**
   - Watch CPU/memory usage
   - Set up alerts for high load
   - Scale vertically if needed

2. **Model Management**
   - Pre-load all required models
   - Use model versioning
   - Document model requirements

3. **High Availability**
   - Consider Ollama replicas for production
   - Implement health checks
   - Set up monitoring

### Distributed Mode

1. **Resource Planning**
   - Calculate memory per agent (~2-4 GB)
   - Plan for model storage duplication
   - Monitor disk usage

2. **Port Management**
   - Document port assignments
   - Use consistent port ranges
   - Avoid conflicts with other services

3. **Model Consistency**
   - Use scripts to sync models across agents
   - Document model versions per agent
   - Test compatibility

---

## Guardian Service Note

**Important:** The Guardian service always maintains its own Ollama instance for security isolation, regardless of the project's model serving mode.

This ensures:
- Security embeddings are isolated
- Guardian can operate independently
- No dependency on shared resources
- Enhanced security posture

---

## Additional Resources

- [ABI-Core Documentation](https://github.com/Joselo-zn/abi-core)
- [Ollama Documentation](https://ollama.ai/docs)
- [Docker Compose Best Practices](https://docs.docker.com/compose/production/)

---

**Last Updated:** December 16, 2024  
**Version:** 1.4.0
