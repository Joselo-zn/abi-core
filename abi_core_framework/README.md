# ABI-Core AI 🤖

[![PyPI version](https://badge.fury.io/py/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![Python](https://img.shields.io/pypi/pyversions/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![License](https://img.shields.io/pypi/l/abi-core-ai.svg)](https://github.com/Joselo-zn/abi-core-ai/blob/main/LICENSE)
[![Documentation](https://readthedocs.org/projects/abi-core/badge/?version=latest)](https://abi-core.readthedocs.io/en/latest/?badge=latest)

**Build AI agents that work together, find each other, and follow the rules.**

ABI-Core is a Python framework for creating AI agents. You write the logic as simple functions, ABI packages them into services, connects them to each other, and makes sure they play by the rules. One `pip install`, one CLI command, and you have a running agent system.

```bash
pip install abi-core-ai
abi-core create swarm --name my-system  # beta
abi-core run
```

> ⚠️ **Beta** — Pipeline works end-to-end. APIs may change between minor versions.

---

## Create an Agent in 3 Files

### 1. Define the steps (`app.py`)

```python
from abi_core.agent import AbiCore
from .my_agent import MyAgent

agent = AbiCore()

@agent.step(name="parse_input")
async def parse_input(raw_input: str) -> dict:
    return {"query": raw_input.strip(), "timestamp": time.time()}

@agent.step(name="process", depends_on=["parse_input"], input_map={"data": "$parse_input.result"})
async def process(data: dict) -> dict:
    result = await invoke(config.LLM_CONFIG, data["query"])
    return {"output": result}

@agent.step(name="respond", depends_on=["process"], input_map={"result": "$process.result"})
async def respond(result: dict) -> dict:
    return {"response": result["output"]}

agent.run(MyAgent())
```

### 2. Define the agent (`my_agent.py`)

```python
from abi_core.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="Processes user queries",
            llm_config={"provider": "ollama", "model": "qwen3:8b", "temperature": 0.3},
            system_prompt="You are a helpful assistant.",
        )
```

### 3. Configure it (`config/config.py`)

```python
import os

AGENT_NAME = "my-agent"
DESCRIPTION = "Processes user queries"
LLM_CONFIG = {"provider": "ollama", "model": "qwen3:8b", "temperature": 0.3}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
```

That's it. `abi-core run` packages and starts your agent with messaging, health checks, and automatic registration.

---

## Key Concepts

### Decorators

| Decorator | What it does |
|-----------|-------------|
| `@agent.step(name, depends_on)` | A function that runs in a fixed order you define |
| `@agent.tool(name)` | A function the AI can decide to call |
| `@agent.mcp_tool(name)` | A remote tool on the Semantic Layer |
| `@agent.task(name, task_id)` | Runs steps in sequence with progress updates |

### Steps run in order

Steps run in the order you define with `depends_on`. Steps at the same level run in parallel. The AI never decides execution order — your code does.

```python
# These two run at the same time (no dependency between them)
@agent.step(name="classify")
async def classify(raw_input): ...

@agent.step(name="validate")
async def validate(raw_input): ...

# This waits for both to finish
@agent.step(name="decide", depends_on=["classify", "validate"],
            input_map={"cls": "$classify.result", "valid": "$validate.result"})
async def decide(cls, valid): ...
```

### invoke() — Call any AI model

```python
from abi_core.agent import invoke

# Simple call
result = await invoke(config.LLM_CONFIG, "Classify this query...")

# With conversation memory
result = await invoke(config.LLM_CONFIG, "Follow up...", thread_id=session_id)

# With tools the AI can use
result = await invoke(config.LLM_CONFIG, "Find...", tools=[search_tool, write_tool])
```

### Agents talk to each other

```python
from abi_core.common.abi_a2a import agent_connection

async for chunk in agent_connection(my_card, target_card, payload):
    process(chunk)
```

---

## CLI

```bash
# Create
abi-core create swarm --name <name>          # Full system: agents + services + compose (beta)
abi-core create project <name>               # Project only
abi-core add agent <name> --description "…"  # Add agent to existing project
abi-core add semantic-layer                  # Add agent discovery service
abi-core add service guardian-native         # Add security gate

# Run
abi-core run                # Start everything
abi-core run --logs         # With container output
abi-core run --build        # Rebuild first
```

---

## Built-in Agents

When you `create swarm`, you get these out of the box:

| Agent | What it does |
|-------|-------------|
| **Orchestrator** | Receives requests, checks security, routes to Planner |
| **Planner** | Breaks complex requests into smaller tasks |
| **Builder** | Creates temporary agents on-demand for specific tasks *(beta)* |
| **Zombie** | Temporary agent — does the work, delivers results, cleans up *(beta)* |

The flow: User → Orchestrator → Planner → Builder → Zombie → Result → Done.

---

## Any AI Model

Switch providers by changing one config dict. Same code, any model:

```python
# Local (Ollama)
{"provider": "ollama", "model": "qwen3:8b"}

# OpenAI
{"provider": "openai", "model": "gpt-4o", "api_key": "..."}

# Anthropic
{"provider": "anthropic", "model": "claude-sonnet-4-20250514"}

# AWS Bedrock
{"provider": "bedrock", "model": "anthropic.claude-3-sonnet"}

# Azure OpenAI
{"provider": "azure", "model": "gpt-4o", "endpoint": "..."}
```

---

## Security

- **Guardian** — checks every request against rules before it runs
- **Signed messages** — agent-to-agent calls are signed and verified
- **Access control** — agents can only use tools they're allowed to
- **Audit trail** — every decision is logged with a risk score
- **Human veto** — you can block execution before it starts

---

## Project Structure

```
my-swarm/
├── agents/
│   ├── orchestrator/     # Receives and routes requests
│   ├── planner/          # Breaks tasks into pieces
│   ├── builder/          # Creates temporary agents
│   └── my-agent/         # Your custom agents
├── services/
│   ├── semantic_layer/   # Agent discovery + search
│   └── guardian/         # Security rules
├── compose.yaml
└── .abi/runtime.yaml
```

---

## Examples

Progressive examples from a simple chatbot to a full multi-agent swarm:

👉 **[abi-core-examples](https://github.com/Joselo-zn/abi-core-examples)** — Includes a step-by-step tutorial for building a multi-agent discussion system.

---

## Documentation

Full docs: [https://abi-core.readthedocs.io](https://abi-core.readthedocs.io)

---

## Contributing

```bash
git clone https://github.com/Joselo-zn/abi-core
cd abi-core-ai
uv sync --dev
uv run pytest
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

**Built by [José Luis Martínez](https://github.com/Joselo-zn)**
