# Troubleshooting

Solutions to common problems.

## Agent Not Responding

**Symptom**: Timeout when calling agent

**Solutions**:
```bash
# 1. Verify it's running
docker-compose ps

# 2. View logs
docker-compose logs my-agent-agent

# 3. Restart
docker-compose restart my-agent-agent
```

## Port in Use

**Symptom**: "Port already in use"

**Solution**: Change port in `compose.yaml`:
```yaml
ports:
  - "9000:8000"  # Use 9000 instead of 8000
```

## Model Not Found

**Symptom**: "Model not found"

**Solution**:
```bash
# Download model
docker exec my-project-ollama ollama pull qwen2.5:3b

# Or reprovision
abi-core provision-models
```

## Slow Agent

**Causes**:
- Model too large
- Low RAM
- Slow CPU

**Solutions**:
```bash
# Use smaller model
docker exec my-project-ollama ollama pull phi3:mini

# Update configuration
# Edit .abi/runtime.yaml:
# model: phi3:mini
```

## Semantic Layer Not Finding Agents

**Solutions**:
```bash
# 1. Verify agent cards exist
ls services/semantic_layer/layer/mcp_server/agent_cards/

# 2. Restart semantic layer
docker-compose restart semantic-layer

# 3. View logs
docker-compose logs semantic-layer
```

## Next Steps

- [Deployment](04-deployment.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
