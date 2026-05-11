# Your First Agent

You have a project. Now let's write an actual agent with steps, a task, and an LLM call.

## Create the agent

```bash
abi-core add agent greeter \
  --description "Greets users and answers questions" \
  --with-web-interface
```

Tasks/skills when prompted:
```
greet_user
```

## Understand the structure

```
agents/greeter/
├── app.py              ← AbiCore instance (import this everywhere)
├── agent_greeter.py    ← Agent class (identity + LLM config)
├── steps.py            ← Your step functions
├── tasks.py            ← Your task functions
├── prompts.py          ← All prompts live here
├── config/config.py    ← LLM provider, ports, env vars
├── web_interface.py    ← HTTP endpoints
├── main.py             ← Entry point: agent.run()
└── Dockerfile
```

## Write a step

A step is a function that does one thing. Edit `agents/greeter/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from prompts import GREET_PROMPT


@agent.step(name="greet")
async def greet(text):
    """Generate a greeting response."""
    result = await invoke(config.LLM_CONFIG, GREET_PROMPT.format(text=text))
    return {"response": result}
```

## Write the prompt

Edit `agents/greeter/prompts.py`:

```python
GREET_PROMPT = """You are a friendly assistant. The user said:

{text}

Respond warmly and helpfully. Keep it short.
"""
```

## Write a task

A task orchestrates steps and streams responses. Edit `agents/greeter/tasks.py`:

```python
import json
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="greet_user", task_id="task-greet")
async def greet_user(query):
    """Greet the user."""
    data = json.loads(query) if isinstance(query, str) else query
    text = data.get("text", "")

    yield AgentResponse.status("Thinking...")
    result = await agent.execute_step("greet", text=text)
    yield AgentResponse.result(result)
```

## Run it

```bash
docker compose up --build -d
```

## Talk to it

```bash
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Hey there!"}'
```

## What happened

1. The web interface received your HTTP request
2. It wrapped your text into the JSON contract: `{"route": "user_request", "text": "Hey there!"}`
3. The task `greet_user` ran
4. It called `agent.execute_step("greet")` which invoked the LLM
5. The response streamed back as SSE events

## Key rules

- Steps are pure functions. They receive data, call `invoke()`, return a dict.
- Tasks orchestrate steps. They `yield` AgentResponse objects for streaming.
- Prompts go in `prompts.py`. Never inline.
- Config goes in `config/config.py`. Never hardcode URLs or model names.

## Next step

👉 [Simple Chatbot](02-simple-chatbot.md)
