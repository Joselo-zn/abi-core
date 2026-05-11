# Troubleshooting

Common problems and how to fix them.

## Agent not responding

```bash
# Is it running?
docker compose ps

# What's in the logs?
docker compose logs --tail=50 my-agent

# Restart it
docker compose restart my-agent
```

## "Model not found"

The LLM model isn't pulled yet:

```bash
docker exec <ollama-container> ollama pull qwen2.5:3b
```

Or check which models are available:

```bash
docker exec <ollama-container> ollama list
```

## Slow responses

**Cause:** Model too large for your hardware.

**Fix:** Use a smaller model:

```python
# config.py
LLM_CONFIG = {"provider": "ollama", "model": "qwen2.5:1.5b"}  # Smaller, faster
```

Or check RAM usage: `docker stats`

## Semantic Layer not finding agents

```bash
# Are agent cards in the right place?
ls services/semantic_layer/agent_cards/

# Is Weaviate healthy?
curl http://localhost:8081/v1/.well-known/ready

# Restart to re-index
docker compose restart <project>-semantic-layer
```

## "Port already in use"

Another process is using that port. Either stop it or change the port in `compose.yaml`:

```yaml
ports:
  - "8003:8002"  # Map to a different host port
```

## A2A connection refused

The target agent isn't ready yet. Check:

```bash
# Is the target running?
docker compose ps

# Can you reach it?
curl http://<target-container>:<port>/health
```

Common cause: the agent depends on Semantic Layer which depends on Weaviate. Wait for health checks to pass.

## "Session terminated" from MCP

The Semantic Layer connection dropped. `MCPToolkit.call_with_retry()` handles this automatically:

```python
result = await toolkit.call_with_retry("my_tool", max_retries=3, param="value")
```

## Container keeps restarting

Check logs for the crash reason:

```bash
docker compose logs --tail=100 <container>
```

Common causes:
- Missing environment variable
- Agent card file not found
- Python import error (missing dependency)

## Next step

👉 [Deployment](04-deployment.md)
