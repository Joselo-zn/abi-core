# Simple Chatbot

A chatbot with multiple steps: it classifies the message, then responds accordingly.

## What you'll build

An agent that:
1. Classifies the user's message (question, greeting, task)
2. Generates a response based on the classification
3. Streams status updates in real-time

## The steps

Edit `agents/chatbot/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke


@agent.step(name="classify")
async def classify(text):
    """Classify the user's intent."""
    prompt = f"""Classify this message into one category: greeting, question, task, other.
Message: {text}
Reply with just the category name."""
    result = await invoke(config.LLM_CONFIG, prompt)
    return {"intent": result.strip().lower()}


@agent.step(name="respond")
async def respond(text, intent):
    """Generate a response based on intent."""
    prompt = f"""You are a helpful chatbot. The user's intent is: {intent}
User message: {text}
Respond naturally and concisely."""
    result = await invoke(config.LLM_CONFIG, prompt)
    return {"response": result}
```

## The task

Edit `agents/chatbot/tasks.py`:

```python
import json
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="chat", task_id="task-chat")
async def chat(query):
    """Classify then respond."""
    data = json.loads(query) if isinstance(query, str) else query
    text = data.get("text", "")

    yield AgentResponse.status("Understanding your message...")
    classification = await agent.execute_step("classify", text=text)

    yield AgentResponse.status(f"Got it — this is a {classification['intent']}...")
    response = await agent.execute_step(
        "respond", text=text, intent=classification["intent"]
    )

    yield AgentResponse.result({
        "intent": classification["intent"],
        "response": response["response"],
    })


@agent.task(name="route_to_task", task_id="task-router")
async def route_to_task(query):
    """All requests go to chat."""
    async for response in agent.execute_task("chat", query=query):
        yield response
```

## Test it

```bash
docker compose up --build -d

curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?"}'
```

You'll see:
```
event: status → "Understanding your message..."
event: status → "Got it — this is a question..."
event: result → {"intent": "question", "response": "Machine learning is..."}
```

## What's different from the first agent

- **Two steps** instead of one — classify and respond are separate, reusable
- **Status updates** — the user sees progress in real-time
- **Structured output** — the result includes both intent and response

## Next step

👉 [Agents with Tools](03-agents-with-tools.md)
