# Plan, Then Execute — Two Agents

In [Plan and Execute](../single-agent/08-plan-and-execute.md) one agent planned and ran every action itself, in-process. Here we split that in two: a **Planner** that turns a request into a list of actions, and an **Executor** that actually carries each one out — connected by a real agent-to-agent (A2A) call. This is the same mechanism the Orchestrator uses to call the Planner in the full swarm (see [Planner & Orchestrator](../orchestration/01-planner-orchestrator.md)), stripped down to its essentials.

We'll write both agents by hand — no `abi-core create project`, no Docker, no Semantic Layer — so every moving part is visible. `abi-core add agent` / `abi-core create swarm` generate the same shapes for you, wired for production (Guardian, OPA, Semantic Layer discovery, containers). Once this clicks, go back to [Your First Multi-Agent System](04-first-multi-agent-system.md) and use the CLI.

## What you'll build

```
planner_agent/
├── app.py
├── main.py
├── config.py
├── agent_card.json
├── web_interface.py     ← minimal HTTP front door, so you can curl it
├── steps.py
└── tasks.py

executor_agent/
├── app.py
├── main.py
├── config.py
├── agent_card.json
├── steps.py
└── tasks.py
```

- **Executor** — one step that carries out a single action. Only reachable via A2A.
- **Planner** — plans the request, then calls the Executor once per action via `AgentInteractionFlow`. Reachable over HTTP so you can talk to it directly.

## Step 1: The executor

`executor_agent/agent_card.json` — with no CLI, we write the A2A card by hand. Only `name`/`description`/`url`/`capabilities` matter here:

```json
{
  "name": "Executor",
  "description": "Carries out a single, concrete action",
  "url": "http://localhost:8101",
  "version": "1.0.0",
  "capabilities": {"streaming": "True", "pushNotifications": "False"},
  "skills": []
}
```

`executor_agent/config.py`:

```python
import os
from abi_core.common.agent_card_loader import load_agent_card

_HERE = os.path.dirname(__file__)


class AgentConfig:
    AGENT_NAME = "executor"
    AGENT_DISPLAY_NAME = "Executor"
    AGENT_DESCRIPTION = "Carries out a single, concrete action"
    AGENT_PORT = int(os.getenv("AGENT_PORT", "8101"))
    AGENT_CARD = os.path.join(_HERE, "agent_card.json")
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_CONFIG = {
        "provider": "ollama",
        "model": MODEL_NAME,
        "temperature": 0.1,
        "base_url": OLLAMA_HOST,
    }
    LOG_LEVEL = "INFO"
    # No Guardian/OPA in this tutorial — see "Key rules" below. These two
    # still need to exist (even unreachable) so the validator reads
    # A2A_VALIDATION_MODE off this config instead of falling back to its
    # own strict-by-default lookup when it can't find them.
    GUARDIAN_URL = os.getenv("GUARDIAN_URL", "http://localhost:11438")
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
    A2A_VALIDATION_MODE = os.getenv("A2A_VALIDATION_MODE", "disabled")
    A2A_ENABLE_AUDIT_LOG = False


config = AgentConfig()
AGENT_CARD, _ = load_agent_card(os.path.join(_HERE, "agent_card.json"))
```

`executor_agent/app.py` — same shape `abi-core add agent` would generate:

```python
from abi_core.agent import AbiCore

agent = AbiCore()
```

`executor_agent/steps.py`:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke


@agent.step(name="run_action")
async def run_action(query):
    """Do the actual work for one action. Swap this for a real tool call —
    hit an API, write a file, query a database."""
    result = await invoke(config.LLM_CONFIG, f"Do this: {query}\nReport what you did.")
    return {"outcome": result}
```

`executor_agent/tasks.py` — `query` arrives exactly as the caller sent it: no automatic JSON wrapping happens anywhere between an A2A call (or an HTTP `{"query": "..."}` body) and your task function. Here it's the plain action text the Planner sent:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="run", task_id="task-run")
async def run(query):
    result = await agent.execute_step("run_action", query=query)
    yield AgentResponse.result(result)
```

`executor_agent/main.py`:

```python
from app import agent
from abi_core.agent.agent import AbiAgent
from config import config


class ExecutorAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[],
            system_prompt="You execute one concrete action and report the outcome.",
            content_types=["text", "text/plain"],
        )


agent.run(ExecutorAgent())
```

## Step 2: The planner

`planner_agent/agent_card.json`:

```json
{
  "name": "Planner",
  "description": "Breaks a request into ordered actions and runs each one",
  "url": "http://localhost:8100",
  "version": "1.0.0",
  "capabilities": {"streaming": "True", "pushNotifications": "False"},
  "skills": []
}
```

`planner_agent/config.py` — identical shape to the executor's, plus `WEB_INTERFACE_PORT` (needed below) and a different port:

```python
import os
from abi_core.common.agent_card_loader import load_agent_card

_HERE = os.path.dirname(__file__)


class AgentConfig:
    AGENT_NAME = "planner"
    AGENT_DISPLAY_NAME = "Planner"
    AGENT_DESCRIPTION = "Breaks a request into ordered actions and runs each one"
    AGENT_PORT = int(os.getenv("AGENT_PORT", "8100"))
    WEB_INTERFACE_PORT = int(os.getenv("WEB_INTERFACE_PORT", "8103"))
    AGENT_CARD = os.path.join(_HERE, "agent_card.json")
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_CONFIG = {
        "provider": "ollama",
        "model": MODEL_NAME,
        "temperature": 0.1,
        "base_url": OLLAMA_HOST,
    }
    LOG_LEVEL = "INFO"
    GUARDIAN_URL = os.getenv("GUARDIAN_URL", "http://localhost:11438")
    OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
    A2A_VALIDATION_MODE = os.getenv("A2A_VALIDATION_MODE", "disabled")
    A2A_ENABLE_AUDIT_LOG = False


config = AgentConfig()
AGENT_CARD, _ = load_agent_card(os.path.join(_HERE, "agent_card.json"))
```

`planner_agent/web_interface.py` — a minimal HTTP front door, just enough to `curl`. Not the full-featured one `abi-core add agent --with-web-interface` generates (session tokens, Open WebUI compatibility) — see [Sessions](../single-agent/07-sessions-multi-turn.md) for that:

```python
import json
import uuid
from fastapi import FastAPI
from fastapi.responses import StreamingResponse


class MinimalWebInterface:
    def __init__(self, agent_instance, interface_name: str = "Web Interface"):
        self.agent_instance = agent_instance
        self.app = FastAPI(title=interface_name)

        @self.app.post("/stream")
        async def stream(request: dict):
            query = request.get("query", "")
            context_id = str(uuid.uuid4())

            async def events():
                async for chunk in self.agent_instance.stream(query, context_id, context_id):
                    yield f"data: {json.dumps({'message': chunk})}\n\n"

            return StreamingResponse(events(), media_type="text/event-stream")
```

`planner_agent/app.py`:

```python
from abi_core.agent import AbiCore
from web_interface import MinimalWebInterface

agent = AbiCore(web_interface_cls=MinimalWebInterface, interface_name="Planner Web Interface")
```

`planner_agent/steps.py` — the `plan` step is the same idea as the single-agent version:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from abi_core.common.utils import clean_llm_json


@agent.step(name="plan")
async def plan(query):
    """Ask the AI to break the request into an ordered list of actions."""
    prompt = f"""Break this request into an ordered list of concrete actions.
Request: {query}

Reply with ONLY this JSON, nothing else:
{{"actions": ["first action", "second action", ...]}}"""
    raw = await invoke(config.LLM_CONFIG, prompt)
    return {"actions": clean_llm_json(raw)["actions"]}
```

`planner_agent/tasks.py` — this is the new part: instead of calling a step in-process, it opens an `AgentInteractionFlow` to the Executor for each action. This is the exact sequence `orchestrator/agent/steps.py::call_planner` uses to call the real Planner agent:

```python
import os

from app import agent
from config import config, AGENT_CARD
from abi_core.agent.agent_response import AgentResponse
from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode
from abi_core.common.agent_card_loader import load_agent_card
from abi_core.common.a2a_response import A2AResponse

_EXECUTOR_CARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "executor_agent", "agent_card.json"
)


async def call_executor(action: str) -> str:
    """Send one action to the Executor and return its reported outcome."""
    executor_card, _ = load_agent_card(_EXECUTOR_CARD_PATH)

    workflow = AgentInteractionFlow()
    node = InteractionFlowNode(
        task=action,
        source_agent_card=AGENT_CARD,
        target_agent_card=executor_card,
        node_key="execute",
        node_label=f"Execute: {action[:40]}",
    )
    workflow.add_node(node)
    workflow.set_source_card(AGENT_CARD)

    results = []
    async for chunk in workflow.run_workflow():
        results.append(chunk)

    for resp in A2AResponse.from_results(results):
        if resp.data:
            return resp.data.get("outcome", str(resp.data))
        if resp.text:
            return resp.text
    return "(no response from executor)"


@agent.task(name="plan_then_execute", task_id="task-plan-then-execute")
async def plan_then_execute(query):
    yield AgentResponse.status("Planning...")
    plan_result = await agent.execute_step("plan", query=query)
    actions = plan_result["actions"]

    outcomes = []
    for i, action in enumerate(actions, 1):
        yield AgentResponse.status(f"Delegating step {i}/{len(actions)} to the executor: {action}")
        outcome = await call_executor(action)
        outcomes.append({"action": action, "outcome": outcome})

    yield AgentResponse.result({"actions": actions, "outcomes": outcomes})


@agent.task(name="route_to_task", task_id="task-router")
async def route_to_task(query):
    async for response in agent.execute_task("plan_then_execute", query=query):
        yield response
```

`planner_agent/main.py`:

```python
from app import agent
from abi_core.agent.agent import AbiAgent
from config import config


class PlannerAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[],
            system_prompt="You break requests into ordered actions.",
            content_types=["text", "text/plain"],
        )


agent.run(PlannerAgent())
```

## Step 3: Run both agents

Ollama needs to be running locally (`ollama serve`) with a model pulled (`ollama pull qwen2.5:3b`). Then, two terminals:

```bash
# Terminal 1
cd executor_agent
python main.py
```

```bash
# Terminal 2
cd planner_agent
python main.py
```

## Step 4: Talk to the planner

```bash
curl -X POST http://localhost:8100/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a haiku about the ocean, then translate it to Spanish"}'
```

You'll see the planner's status updates stream in, then a result with both actions and both outcomes — the second one produced by a completely separate process.

## What happened

1. Your `curl` hit the Planner's minimal `/stream` endpoint
2. `plan_then_execute` called the `plan` step — one AI call, in-process, same as the single-agent version
3. For each action, `call_executor` opened an `AgentInteractionFlow` and sent the action to the Executor's real A2A endpoint (`http://localhost:8101`)
4. The Executor — a separate Python process — ran its `run` task, called `run_action`, and returned the outcome over A2A
5. The Planner collected each outcome and returned everything to you

## Key rules

- `AgentInteractionFlow`/`InteractionFlowNode` is a real network hop between two processes — contrast with [Plan and Execute](../single-agent/08-plan-and-execute.md), where `agent.execute_step` never leaves the process.
- `target_agent_card` can be loaded directly from a file, as here. The Semantic Layer (used in [Your First Multi-Agent System](04-first-multi-agent-system.md)) is only needed when the set of agents isn't fixed and known ahead of time — i.e. when you need to *discover* who can do the work, not just call them.
- `A2A_VALIDATION_MODE=disabled` skips Guardian/OPA validation entirely. That's fine here — it's development, on your machine. Production wants real governance; see [Guardian Service](../security/01-guardian-service.md).
- The Executor has no web interface — nothing outside the swarm should be able to call it directly except the Planner.

## Next step

👉 [The Semantic Layer — How Discovery Works](../semantic-layer/01-what-is-semantic-layer.md)
