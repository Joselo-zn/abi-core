# Testing and Debugging Agents

Learn to test and debug your agents effectively.

## Basic Testing

### With curl
```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "context_id": "test", "task_id": "1"}'
```

### With Python
```python
import requests

def test_agent(query):
    response = requests.post(
        "http://localhost:8000/stream",
        json={"query": query, "context_id": "test", "task_id": "1"}
    )
    assert response.status_code == 200
    assert 'content' in response.json()
    print(f"✅ Test passed: {query}")

test_agent("Hello")
test_agent("What is Python?")
```

## View Logs

```bash
# Real-time logs
docker-compose logs -f my-agent-agent

# Last 100 lines
docker-compose logs --tail=100 my-agent-agent
```

## Debugging

### Add Logs
```python
from abi_core.common.utils import abi_logging

def process(self, enriched_input):
    abi_logging(f"INPUT: {enriched_input}")
    # ... your code
    abi_logging(f"OUTPUT: {result}")
    return result
```

### Test Locally
```python
# test_local.py
from agents.my_agent.agent_my_agent import MyAgent
import os

os.environ['MODEL_NAME'] = 'qwen2.5:3b'
os.environ['OLLAMA_HOST'] = 'http://localhost:11434'

agent = MyAgent()
result = agent.handle_input("test")
print(result)
```

## Next Steps

- [Multiple agents](../multi-agent-basics/01-why-multiple-agents.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
