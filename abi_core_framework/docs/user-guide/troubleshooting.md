# Troubleshooting Guide

## Common Issues and Solutions

This guide covers common problems you might encounter when using ABI-Core and how to resolve them.

## Installation Issues

### pip install fails

**Problem:**
```bash
ERROR: Could not find a version that satisfies the requirement abi-core-ai
```

**Solution:**
```bash
# Update pip
pip install --upgrade pip

# Install with specific Python version
python3.11 -m pip install abi-core-ai

# Install from source
git clone https://github.com/Joselo-zn/abi-core-ai
cd abi-core-ai
pip install -e .
```

### Python version mismatch

**Problem:**
```
ERROR: abi-core-ai requires Python >=3.11
```

**Solution:**
```bash
# Check Python version
python --version

# Use Python 3.11+
python3.11 -m pip install abi-core-ai

# Or use pyenv
pyenv install 3.11.0
pyenv local 3.11.0
```

## Project Creation Issues

### Command not found

**Problem:**
```bash
abi-core: command not found
```

**Solution:**
```bash
# Ensure package is installed
pip install abi-core-ai

# Check installation
pip show abi-core-ai

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"

# Or use full path
python -m abi_core.cli.main --help
```

### Template directory not found

**Problem:**
```
Error: Template directory not found: scaffolnding
```

**Solution:**
This was a typo in older versions. Update to latest:
```bash
pip install --upgrade abi-core-ai
```

## Model Provisioning Issues

### Ollama not starting

**Problem:**
```
Error: Could not connect to Ollama service
```

**Solution:**
```bash
# Check if Ollama container is running
docker-compose ps

# Check Ollama logs
docker-compose logs ollama

# Restart Ollama
docker-compose restart ollama

# Check Ollama health
curl http://localhost:11434/api/tags
```

### Model download fails

**Problem:**
```
Error downloading model: connection timeout
```

**Solution:**
```bash
# Check internet connection
ping ollama.ai

# Increase timeout
docker-compose exec ollama ollama pull qwen2.5:3b --timeout 300

# Try different model
docker-compose exec ollama ollama pull phi3:mini

# Check disk space
df -h
```

### Model not found after download

**Problem:**
```
Error: model 'qwen2.5:3b' not found
```

**Solution:**
```bash
# List available models
docker-compose exec ollama ollama list

# Pull model explicitly
docker-compose exec ollama ollama pull qwen2.5:3b

# Check model name in runtime.yaml
cat .abi/runtime.yaml

# Restart agent
docker-compose restart my-agent
```

## Agent Issues

### Agent won't start

**Problem:**
```
Error: Agent container exited with code 1
```

**Solution:**
```bash
# Check agent logs
docker-compose logs my-agent

# Common issues:
# 1. Port already in use
docker-compose ps  # Check ports
# Change port in .abi/runtime.yaml

# 2. Ollama not accessible
docker-compose exec my-agent curl http://ollama:11434/api/tags

# 3. Missing dependencies
docker-compose exec my-agent pip list

# Rebuild agent
docker-compose build my-agent
docker-compose up -d my-agent
```

### Agent returns errors

**Problem:**
```json
{"error": "Internal server error"}
```

**Solution:**
```bash
# Check agent logs for details
docker-compose logs -f my-agent

# Common errors:

# 1. Model not loaded
docker-compose exec ollama ollama list
docker-compose exec ollama ollama pull qwen2.5:3b

# 2. Out of memory
docker stats  # Check memory usage
# Reduce model size or increase Docker memory

# 3. Syntax error in agent code
docker-compose exec my-agent python -m py_compile agents/my_agent/agent_my_agent.py
```

### Agent not responding

**Problem:**
Agent endpoint times out or hangs.

**Solution:**
```bash
# Check if agent is running
docker-compose ps my-agent

# Check agent health
curl http://localhost:8000/health

# Check Ollama connection
docker-compose exec my-agent curl http://ollama:11434/api/tags

# Check for deadlocks in logs
docker-compose logs my-agent | grep -i "error\|timeout\|deadlock"

# Restart agent
docker-compose restart my-agent
```

## Semantic Layer Issues

### Agent not found

**Problem:**
```json
{"error": "No agent found for query"}
```

**Solution:**
```bash
# Check if agent cards exist
ls services/semantic_layer/layer/mcp_server/agent_cards/

# Verify agent card format
cat services/semantic_layer/layer/mcp_server/agent_cards/my_agent.json

# Restart semantic layer to reload cards
docker-compose restart semantic-layer

# Check semantic layer logs
docker-compose logs semantic-layer

# Test find_agent directly
curl -X POST http://localhost:8765/v1/tools/find_agent \
  -H "Content-Type: application/json" \
  -d '{"query": "find any agent"}'
```

### Weaviate connection error

**Problem:**
```
Error: Could not connect to Weaviate
```

**Solution:**
```bash
# Check if Weaviate is running
docker-compose ps weaviate

# Check Weaviate health
curl http://localhost:8080/v1/.well-known/ready

# Check Weaviate logs
docker-compose logs weaviate

# Restart Weaviate
docker-compose restart weaviate

# Wait for Weaviate to be ready
until curl -f http://localhost:8080/v1/.well-known/ready; do
  echo "Waiting for Weaviate..."
  sleep 2
done
```

### Embedding errors

**Problem:**
```
Error: Failed to generate embeddings
```

**Solution:**
```bash
# Check if embedding model is available
docker-compose exec ollama ollama list | grep nomic-embed

# Pull embedding model
docker-compose exec ollama ollama pull nomic-embed-text:v1.5

# Test embedding generation
curl -X POST http://localhost:8765/v1/embeddings \
  -d '{"text": "test"}'

# Check semantic layer logs
docker-compose logs semantic-layer | grep -i "embed"
```

## Guardian/OPA Issues

### OPA not starting

**Problem:**
```
Error: OPA service not available
```

**Solution:**
```bash
# Check OPA status
docker-compose ps guardian-opa

# Check OPA logs
docker-compose logs guardian-opa

# Test OPA health
curl http://localhost:8181/health

# Restart OPA
docker-compose restart guardian-opa
```

### Policy errors

**Problem:**
```
Error: Policy evaluation failed
```

**Solution:**
```bash
# Check policy syntax
docker-compose exec guardian-opa opa check /app/opa/policies/

# Test policy
docker-compose exec guardian-opa opa test /app/opa/policies/

# View OPA logs
docker-compose logs guardian-opa

# Test policy directly
curl -X POST http://localhost:8181/v1/data/abi/semantic_access \
  -d '{"input": {"action": "test"}}'
```

### Policy not loading

**Problem:**
Policy changes not taking effect.

**Solution:**
```bash
# Check if policy file exists
docker-compose exec guardian-opa ls /app/opa/policies/

# Restart OPA to reload policies
docker-compose restart guardian-opa

# Check OPA bundle status
curl http://localhost:8181/v1/status

# Verify policy is loaded
curl http://localhost:8181/v1/policies
```

## Docker Issues

### Port conflicts

**Problem:**
```
Error: Port 8000 is already in use
```

**Solution:**
```bash
# Find what's using the port
lsof -i :8000
# or
netstat -tulpn | grep 8000

# Kill the process
kill -9 <PID>

# Or change port in .abi/runtime.yaml
# Then restart
docker-compose down
docker-compose up -d
```

### Out of disk space

**Problem:**
```
Error: No space left on device
```

**Solution:**
```bash
# Check disk space
df -h

# Clean Docker
docker system prune -a

# Remove unused volumes
docker volume prune

# Remove old images
docker image prune -a

# Check Docker disk usage
docker system df
```

### Container keeps restarting

**Problem:**
Container in restart loop.

**Solution:**
```bash
# Check logs
docker-compose logs <service-name>

# Check exit code
docker-compose ps

# Common causes:
# 1. Configuration error - check .abi/runtime.yaml
# 2. Missing dependency - check requirements.txt
# 3. Port conflict - check ports in compose.yaml
# 4. Memory limit - increase Docker memory

# Stop restart loop
docker-compose stop <service-name>

# Fix issue, then start
docker-compose up -d <service-name>
```

## Network Issues

### Services can't communicate

**Problem:**
```
Error: Connection refused to http://other-service:8000
```

**Solution:**
```bash
# Check if services are on same network
docker network inspect <project>-network

# Check service names in compose.yaml
docker-compose config

# Test connectivity
docker-compose exec service1 ping service2
docker-compose exec service1 curl http://service2:8000/health

# Restart network
docker-compose down
docker-compose up -d
```

### DNS resolution fails

**Problem:**
```
Error: Could not resolve hostname
```

**Solution:**
```bash
# Check Docker DNS
docker-compose exec my-agent cat /etc/resolv.conf

# Use IP instead of hostname temporarily
docker inspect <container> | grep IPAddress

# Restart Docker daemon
sudo systemctl restart docker

# Recreate containers
docker-compose down
docker-compose up -d
```

## Performance Issues

### Slow responses

**Problem:**
Agent takes too long to respond.

**Solution:**
```bash
# Check resource usage
docker stats

# Common causes:

# 1. CPU bottleneck
# Use smaller model
# Add more CPU cores

# 2. Memory bottleneck
# Increase Docker memory limit
# Use smaller model

# 3. Disk I/O
# Use SSD
# Increase disk cache

# 4. Network latency
# Check network with: docker-compose exec agent ping ollama

# Monitor specific container
docker stats my-agent
```

### High memory usage

**Problem:**
System running out of memory.

**Solution:**
```bash
# Check memory usage
docker stats

# Solutions:

# 1. Use smaller models
# qwen2.5:3b instead of llama3.1:8b

# 2. Use centralized model serving
# Edit .abi/runtime.yaml:
# model_serving: centralized

# 3. Limit container memory
# In compose.yaml:
# mem_limit: 4g

# 4. Increase system memory
# Or reduce number of agents
```

## Development Issues

### Code changes not reflected

**Problem:**
Changes to agent code don't take effect.

**Solution:**
```bash
# Rebuild container
docker-compose build my-agent

# Restart with new build
docker-compose up -d my-agent

# Or force recreate
docker-compose up -d --force-recreate my-agent

# For development, use volume mounts
# In compose.yaml:
# volumes:
#   - ./agents/my_agent:/app/agents/my_agent
```

### Import errors

**Problem:**
```python
ModuleNotFoundError: No module named 'abi_core'
```

**Solution:**
```bash
# In container, install package
docker-compose exec my-agent pip install abi-core-ai

# Or add to requirements.txt
echo "abi-core-ai" >> agents/my_agent/requirements.txt

# Rebuild
docker-compose build my-agent
docker-compose up -d my-agent
```

### Debugging agents

**Problem:**
Need to debug agent code.

**Solution:**
```bash
# View logs in real-time
docker-compose logs -f my-agent

# Add debug logging in agent code
from abi_core.common.utils import abi_logging
abi_logging(f"Debug: {variable}")

# Enter container for debugging
docker-compose exec my-agent bash

# Run Python REPL
docker-compose exec my-agent python

# Test agent code directly
docker-compose exec my-agent python -c "from agents.my_agent.agent_my_agent import MyAgent; agent = MyAgent(); print(agent)"
```

## Getting Help

### Collect Diagnostic Information

```bash
# System info
uname -a
docker --version
docker-compose --version
python --version

# ABI-Core version
pip show abi-core-ai

# Project status
abi-core status

# Service status
docker-compose ps

# Recent logs
docker-compose logs --tail=100 > logs.txt

# Configuration
cat .abi/runtime.yaml
cat compose.yaml
```

### Report Issues

When reporting issues, include:

1. **Error message** (full stack trace)
2. **Steps to reproduce**
3. **System information** (OS, Docker version, Python version)
4. **ABI-Core version**
5. **Relevant logs**
6. **Configuration files** (runtime.yaml, compose.yaml)

**GitHub Issues:** https://github.com/Joselo-zn/abi-core-ai/issues

### Community Support

- **Discussions:** https://github.com/Joselo-zn/abi-core-ai/discussions
- **Email:** jl.mrtz@gmail.com
- **Documentation:** https://abi-core.readthedocs.io

## Quick Fixes Checklist

When something goes wrong, try these in order:

1. ✅ Check logs: `docker-compose logs <service>`
2. ✅ Restart service: `docker-compose restart <service>`
3. ✅ Check health: `curl http://localhost:<port>/health`
4. ✅ Verify configuration: `cat .abi/runtime.yaml`
5. ✅ Rebuild: `docker-compose build <service>`
6. ✅ Full restart: `docker-compose down && docker-compose up -d`
7. ✅ Check disk space: `df -h`
8. ✅ Check memory: `docker stats`
9. ✅ Update ABI-Core: `pip install --upgrade abi-core-ai`
10. ✅ Check documentation: https://abi-core.readthedocs.io

## Next Steps

- [FAQ](../faq.md) - Frequently asked questions
- [Complete Example](complete-example.md) - Working example
- [Agent Development](agent-development.md) - Build custom agents
