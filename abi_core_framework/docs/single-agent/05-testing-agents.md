# Testing Agents

How to verify your agent works before deploying.

## Quick test with curl

```bash
# Health check
curl http://localhost:8002/health

# Send a query
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}'
```

## Test with Python

```python
import requests

def ask(query, context_id="test"):
    resp = requests.post(
        "http://localhost:8002/stream",
        json={"query": query, "context_id": context_id}
    )
    return resp.json()

# Test basic response
result = ask("What is 2 + 2?")
print(result)

# Test memory
ask("My name is Ana", context_id="mem-test")
result = ask("What's my name?", context_id="mem-test")
assert "Ana" in str(result)
print("✅ Memory works")
```

## View logs

```bash
# All services
docker compose logs -f

# Just your agent
docker compose logs -f my-agent

# Last 50 lines
docker compose logs --tail=50 my-agent
```

## Add logging to your code

```python
from abi_core.common.utils import abi_logging

@agent.step(name="my_step")
async def my_step(text):
    abi_logging(f"[📥] Input: {text}")
    result = await invoke(config.LLM_CONFIG, prompt)
    abi_logging(f"[📤] Output: {result[:100]}")
    return {"result": result}
```

Logs show up in `docker compose logs` with timestamps.

## Common issues

**Agent returns empty response** — Check that Ollama is running and the model is pulled:
```bash
docker exec <ollama-container> ollama list
```

**Connection refused** — The agent container isn't ready yet. Wait a few seconds or check:
```bash
docker compose ps
```

**LLM timeout** — The model is too large for your hardware. Try a smaller model in `config.py`:
```python
LLM_CONFIG = {"provider": "ollama", "model": "qwen2.5:1.5b"}
```

## Next step

👉 [Why Multiple Agents?](../multi-agent-basics/01-why-multiple-agents.md)
