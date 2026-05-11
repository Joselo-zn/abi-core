# ABI-Core AI 🤖

[![PyPI version](https://badge.fury.io/py/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![Python](https://img.shields.io/pypi/pyversions/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![License](https://img.shields.io/pypi/l/abi-core-ai.svg)](https://github.com/Joselo-zn/abi-core-ai/blob/main/LICENSE)
[![Documentation](https://readthedocs.org/projects/abi-core/badge/?version=latest)](https://abi-core.readthedocs.io/en/latest/?badge=latest)

**Build AI agents with deterministic DAG execution, semantic discovery, and governed autonomy.**

ABI-Core is a Python framework for creating agents that run as containerized services with structured execution graphs, inter-agent communication, and policy-driven security. One `pip install`, one CLI command, and you have a running agent system.

```bash
pip install abi-core-ai
abi-core create swarm --name my-system
abi-core run
```

> ⚠️ **Beta** — Pipeline is functional end-to-end. APIs may change between minor versions.

---

## Create an Agent in 3 Files

### 1. Define the DAG (`app.py`)

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

### 2. Define the Agent Class (`my_agent.py`)

```python
from abi_core.agent import AbiAgent

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="Processes user queries with structured reasoning",
            llm_config={"provider": "ollama", "model": "qwen3:8b", "temperature": 0.3},
            system_prompt="You are a helpful assistant that...",
        )
```

### 3. Configure Identity (`config/config.py`)

```python
import os

AGENT_NAME = "my-agent"
DESCRIPTION = "Processes user queries with structured reasoning"
LLM_CONFIG = {"provider": "ollama", "model": "qwen3:8b", "temperature": 0.3}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
```

That's it. `abi-core run` containerizes and starts your agent with A2A protocol, health checks, and semantic registration.

---

## Key Concepts

### Decorator API

| Decorator | Purpose |
|-----------|---------|
| `@agent.step(name, depends_on, input_map)` | Deterministic DAG node — compiled at init, executed per request |
| `@agent.tool(name)` | DAG node + LangChain tool — LLM can invoke on demand |
| `@agent.mcp_tool(name)` | Remote tool via MCP protocol with HMAC auth |
| `@agent.task(name, tools)` | Programmatic orchestrator — manual step execution with branching |

### DAG Execution

Steps registered with `@agent.step()` compile into a `ToolExecutionGraph` (LangGraph). Nodes at the same dependency level run in parallel. The LLM never decides execution order — the graph does.

```python
# These two run in parallel (no dependencies between them)
@agent.step(name="classify")
async def classify(raw_input): ...

@agent.step(name="validate")
async def validate(raw_input): ...

# This waits for both
@agent.step(name="decide", depends_on=["classify", "validate"],
            input_map={"cls": "$classify.result", "valid": "$validate.result"})
async def decide(cls, valid): ...
```

### invoke() — Unified LLM Calls

```python
from abi_core.agent import invoke

# Simple LLM call
result = await invoke(config.LLM_CONFIG, "Classify this query...")

# With conversation memory
result = await invoke(config.LLM_CONFIG, "Follow up...", thread_id=session_id)

# With tools
result = await invoke(config.LLM_CONFIG, "Find...", tools=[search_tool, write_tool])
```

### Inter-Agent Communication

Agents talk to each other via A2A protocol using `AgentInteractionFlow`:

```python
from abi_core.common.workflow import AgentInteractionFlow

flow = AgentInteractionFlow(source_agent="my-agent", target_agent="planner", host=planner_url)
async for event in flow.stream(query="Decompose this task"):
    process(event)
```

---

## CLI

```bash
# Scaffold
abi-core create swarm --name <name>          # Full system: agents + services + compose
abi-core create project <name>               # Project only
abi-core add agent <name> --description "…"  # Add agent to existing project
abi-core add semantic-layer                  # Add Weaviate semantic discovery
abi-core add service guardian-native         # Add OPA security gate

# Run
abi-core run                # Detached (status table)
abi-core run --logs         # With container output
abi-core run --build        # Rebuild containers first
```

---

## Built-in Agents

When you `create swarm`, you get these out of the box:

| Agent | Role |
|-------|------|
| **Orchestrator** | Entry point. Triage + Guardian gate + routes to Planner |
| **Planner** | Decomposes queries into structured task plans |
| **Builder** | Spawns ephemeral containers from task specs |
| **Zombie** | Ephemeral executor — runs task, uploads artifacts, self-destructs |

The pipeline: User → Orchestrator → Planner → Builder → Zombie → Artifact → Done.

---

## Multi-Provider LLM

```python
# Ollama (local, default)
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

## Security & Governance

- **Guardian Agent** — validates every request against OPA policies before execution
- **HMAC Authentication** — inter-agent calls are signed and verified
- **Semantic Access Validation** — agents can only call tools within their `access_scope`
- **Audit Trail** — all decisions logged with risk scores
- **Human Veto** — Plan Confirmation allows blocking execution before it starts

---

## Project Structure

```
my-swarm/
├── agents/
│   ├── orchestrator/     # Triage + routing
│   ├── planner/          # Task decomposition
│   ├── builder/          # Container spawning
│   └── my-agent/         # Your custom agents
├── services/
│   ├── semantic_layer/   # Weaviate + MCP tools
│   └── guardian/         # OPA policies
├── compose.yaml
└── .abi/runtime.yaml
```

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
