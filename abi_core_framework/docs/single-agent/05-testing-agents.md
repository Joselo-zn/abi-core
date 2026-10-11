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

## Talk to it from Python

`AgentStreamClient` (`abi_core.client.agent_stream_client`) is the same client the bundled Chainlit UI uses. It starts a session once, sends the token on every message, decodes each streamed event into a plain dict, and fetches a fresh token if the old one expired. Use one instance per conversation:

```python
import asyncio
from abi_core.client.agent_stream_client import AgentStreamClient


async def ask(client, query):
    """Send a query; print progress as it streams; return the final answer."""
    answer = None
    async for event in client.stream(query):
        print(event.get("response_type", "-"), "→", event.get("content"))
        if event.get("is_task_completed"):
            answer = event.get("content")
    return answer


async def main():
    client = AgentStreamClient("http://localhost:8002")

    print(await ask(client, "What is 2 + 2?"))

    # Same client = same session = same conversation
    await ask(client, "My name is Ana")
    answer = await ask(client, "What's my name?")
    assert "Ana" in str(answer)
    print("✅ Memory works")


asyncio.run(main())
```

Each event has the shape `AgentResponse` produces on the server: `response_type` (`status`, `text`, `data`, `input_required`, `error`), `content`, and optional `meta`. The final answer is the event with `is_task_completed: True`; the stream then closes with a short `{"content": "Stream completed successfully"}` notice. A connection failure comes back as one `{"response_type": "error", ...}` event instead of an exception, so you can treat every item the same way.

The memory check only passes if your agent stores the conversation — see [Agents with Memory](04-agents-with-memory.md).

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

**LLM timeout** — The model is too large for your hardware. Try a smaller model:

```bash
docker exec ollama ollama pull qwen3:1.7b
```

Then set `MODEL_NAME=qwen3:1.7b` on the agent in `compose.yaml` and restart it (`docker compose up -d <agent>`).

## Next step

👉 [Why Multiple Agents?](../multi-agent-basics/01-why-multiple-agents.md)
