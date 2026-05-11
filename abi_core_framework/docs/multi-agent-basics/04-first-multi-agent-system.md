# Your First Multi-Agent System

Build a system where a coordinator agent finds and calls a worker agent through the Semantic Layer.

## What you'll build

Two agents:
- **Coordinator** — receives user requests, finds the right agent, delegates work
- **Researcher** — answers research questions when called

## Step 1: Create the project

```bash
abi-core create project multi-demo --with-semantic-layer
cd multi-demo
```

## Step 2: Add the agents

```bash
abi-core add agent coordinator \
  --description "Receives requests and delegates to specialized agents" \
  --with-web-interface

# Tasks: coordinate_request

abi-core add agent researcher \
  --description "Researches topics and provides detailed answers"

# Tasks: research_topic
```

## Step 3: Write the Researcher

Edit `agents/researcher/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke


@agent.step(name="research")
async def research(topic):
    """Research a topic in depth."""
    prompt = f"""You are a research specialist. Provide a detailed,
well-structured answer about: {topic}

Include key facts, context, and implications. 2-3 paragraphs max."""
    result = await invoke(config.LLM_CONFIG, prompt)
    return {"answer": result}
```

Edit `agents/researcher/tasks.py`:

```python
import json
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="research_topic", task_id="task-research")
async def research_topic(query):
    data = json.loads(query) if isinstance(query, str) else query
    topic = data.get("text", data.get("topic", ""))

    yield AgentResponse.status("Researching...")
    result = await agent.execute_step("research", topic=topic)
    yield AgentResponse.result(result)
```

## Step 4: Write the Coordinator

Edit `agents/coordinator/steps.py`:

```python
import json
from app import agent
from config import config
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.common.abi_a2a import agent_connection


@agent.step(name="find_worker")
async def find_worker(task_description):
    """Find an agent that can handle this task."""
    agent_card = await tool_find_agent.ainvoke(task_description)
    return {"worker": agent_card}


@agent.step(name="delegate")
async def delegate(worker, message, source_card):
    """Send work to another agent via A2A."""
    payload = {
        "message": {
            "messageId": "delegate-001",
            "role": "user",
            "parts": [{"text": json.dumps({"text": message})}],
        }
    }

    response_text = ""
    async for chunk in agent_connection(source_card, worker, payload):
        if hasattr(chunk, 'root') and hasattr(chunk.root, 'result'):
            result = chunk.root.result
            if hasattr(result, 'status') and hasattr(result.status, 'message'):
                for part in result.status.message.parts:
                    if hasattr(part, 'text'):
                        response_text = part.text

    return {"response": response_text}
```

Edit `agents/coordinator/tasks.py`:

```python
import json
from app import agent
from abi_core.agent.agent_response import AgentResponse
from config import AGENT_CARD


@agent.task(name="coordinate_request", task_id="task-coordinate")
async def coordinate_request(query):
    data = json.loads(query) if isinstance(query, str) else query
    text = data.get("text", "")

    # Find a worker
    yield AgentResponse.status("🔍 Finding the right agent...")
    discovery = await agent.execute_step("find_worker", task_description=text)
    worker = discovery["worker"]

    if not worker:
        yield AgentResponse.error("No agent found for this task.")
        return

    yield AgentResponse.status(f"📡 Delegating to {worker.name}...")

    # Call the worker via A2A
    result = await agent.execute_step(
        "delegate", worker=worker, message=text, source_card=AGENT_CARD
    )

    yield AgentResponse.result({
        "delegated_to": worker.name,
        "response": result["response"],
    })


@agent.task(name="route_to_task", task_id="task-router")
async def route_to_task(query):
    async for response in agent.execute_task("coordinate_request", query=query):
        yield response
```

## Step 5: Run it

```bash
docker compose up ollama -d
docker exec multi-demo-ollama ollama pull qwen2.5:3b
docker exec multi-demo-ollama ollama pull nomic-embed-text:v1.5
docker compose up --build -d
```

## Step 6: Test it

```bash
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Research the impact of quantum computing on cryptography"}'
```

You'll see:
```
event: status → "🔍 Finding the right agent..."
event: status → "📡 Delegating to researcher..."
event: result → {"delegated_to": "researcher", "response": "Quantum computing poses..."}
```

## What happened

1. User sent a request to the coordinator's web interface
2. Coordinator searched the Semantic Layer for "research" capability
3. Found the researcher agent's card (matched by description + skills)
4. Called the researcher via A2A protocol (HMAC validated)
5. Researcher executed its `research_topic` task, called the LLM
6. Response streamed back through A2A to the coordinator
7. Coordinator forwarded the result to the user via SSE

## Next step

👉 [Semantic Layer — How Discovery Works](../semantic-layer/01-what-is-semantic-layer.md)
