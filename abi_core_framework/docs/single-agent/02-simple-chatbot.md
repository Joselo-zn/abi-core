# Simple Chatbot

A chatbot with multiple steps: it classifies the message, then responds accordingly.

## What you'll build

An agent that:
1. Classifies the user's message (question, greeting, task)
2. Generates a response based on the classification
3. Streams status updates in real-time

## Create the agent

```bash
abi-core add agent --name chatbot \
  --description "Classifies messages and answers them" \
  --with-web-interface
```

When it asks for tasks/skills, type `chat`.

## The steps

Replace the contents of `agents/chatbot/steps.py`:

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

Replace the contents of `agents/chatbot/tasks.py`:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="chat", task_id="task-chat")
async def chat(query):
    """Classify then respond."""
    text = query  # the text exactly as the user sent it

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

Why the second task? When a request arrives, the agent picks the task to run in this order: the task whose `task_id` matches the request's `task_id`, then a task named `route_to_task` (or `main`), then the first task registered. A `route_to_task` makes the entry point explicit instead of depending on file order — and it's the natural place to branch to different tasks later.

## Test it

```bash
docker compose up --build -d

curl -N -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?"}'
```

You'll see one `data:` line per update (`curl -N` prints them as they arrive). Each line wraps one `AgentResponse`:

```
data: {"message": "{'response_type': 'status', 'content': 'Understanding your message...', 'is_task_completed': False, ...}", "type": "dict"}
data: {"message": "{'response_type': 'status', 'content': 'Got it — this is a question...', 'is_task_completed': False, ...}", "type": "dict"}
data: {"message": "{'response_type': 'data', 'content': {'intent': 'question', 'response': 'Machine learning is...'}, 'is_task_completed': True, ...}", "type": "dict"}
```

`AgentResponse.status(...)` arrives as `response_type: status`, `AgentResponse.result(...)` as `response_type: data` with `is_task_completed: True`. You don't need to unpack this by hand — [`AgentStreamClient`](05-testing-agents.md#talk-to-it-from-python) does it for you. The rest of these docs abbreviate the stream as `event: status → "..."` / `event: result → {...}`.

## What's different from the first agent

- **Two steps** instead of one — classify and respond are separate, reusable
- **Status updates** — the user sees progress in real-time
- **Structured output** — the result includes both intent and response

## Give it a chat UI

Instead of `curl`, add a [Chainlit](https://docs.chainlit.io) chat interface. It's added
as a Docker service and started with the rest of the stack — no separate process:

```bash
abi-core add chainlit     # auto-detects your web agent from .abi
abi-core run              # starts the UI too; it prints the URL (e.g. http://localhost:8500)
```

The UI opens a framework-managed session, so follow-up messages keep their context
(multi-turn). See the [CLI reference](../reference/cli-reference.md#abi-core-add-chainlit)
for options.

## Next step

👉 [Agents with Tools](03-agents-with-tools.md)
