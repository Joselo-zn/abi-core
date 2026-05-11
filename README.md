# ABI – Agent-Based Infrastructure
Created and maintained by José Luis Martínez

**ABI** is an open-source framework for building distributed, self-organizing multi-agent systems that run on your own hardware.

Instead of wiring LLMs to tools behind API calls, ABI implements a full infrastructure where agents discover each other semantically, decompose tasks into plans, spawn ephemeral workers in containers, execute with injected tools, upload artifacts, and clean up after themselves. All auditable, all governed by policy, all local-first.

This repository contains the **ABI-Core framework** — the runtime, CLI, and building blocks to create, deploy, and operate multi-agent swarms from a single `pip install abi-core-ai`.

## Why ABI?

Most agent frameworks solve how to wire an LLM to tools. ABI solves a different problem: how to build a system where multiple agents collaborate, self-organize, and operate under governance — without depending on a single vendor, a single model, or a centralized API.

| | ABI-Core | LangGraph / CrewAI / AutoGen |
|---|---|---|
| Architecture | Distributed swarm with semantic discovery | Centralized graph or crew definition |
| Agent lifecycle | Ephemeral containers — spawn, execute, self-destruct *(beta)* | Long-running processes |
| Tool discovery | Semantic layer (Weaviate) — agents find each other by meaning | Hardcoded tool lists or registries |
| Security | OPA policies + Guardian agent + HMAC per request | Varies, usually app-level |
| Model serving | Local-first (Ollama), vendor-agnostic | Typically API-dependent (OpenAI, etc.) |
| Scaffolding | Full CLI: `abi-core create swarm` generates everything | Manual setup or minimal templates |
| Governance | Built-in: audit logs, human veto, policy engine | Not included |
| Deployment | Docker Compose ready, one command | Manual container setup |
| Target | Universities, NGOs, labs, open-source communities | Developers building single-purpose agents |

## Core Principles

### 1. Semantic-First
Agents discover each other by meaning, not configuration. The Semantic Router queries Weaviate for the most relevant agent via embeddings — no hardcoded routes, no manual registries.

### 2. Ephemeral by Design *(beta)*
Execution agents are born, work, and die. The Builder creates Docker containers with injected tools, the Zombie executes, uploads artifacts to MinIO, deregisters from Weaviate, and the container self-destructs. No residual state.

### 3. Human Veto Always
No agent acts without oversight. The Guardian validates every request against OPA policies before execution. Plan Confirmation (next milestone) lets users approve or reject plans before they run. Emergency shutdown is always available.

### 4. Local-First, Vendor-Agnostic
Everything runs on your hardware with Ollama. No API keys, no data leaving your network. The Processor Interface abstracts the model — use qwen, llama, mistral, or any compatible model without changing code.

### 5. Governed Autonomy
Agents collaborate freely within policy-defined boundaries. Immutable OPA policies control what each agent can do. Immutable audit logs record every decision. Agents cannot modify their own rules.

### 6. Composable Infrastructure
Everything is modular and extensible. `abi-core create swarm` generates a complete project. `abi-core add agent` adds agents. TUI widgets are reusable. Jinja2 templates are customizable. Each piece works standalone or as part of the swarm.

## 🚀 What's Working

The end-to-end pipeline is functional and verified:

```
User query
  → Orchestrator (triage + Guardian security gate)
    → Planner (decomposes into tasks with steps + model recommendation)
      → Builder (finds or creates agents, spawns ephemeral Docker containers)
        → Zombie (executes with injected tools, uploads artifacts to MinIO)
          → Self-deregisters from Weaviate, container self-destructs
            → Orchestrator synthesizes result and responds
```

### Agents

| Agent | Role | Status |
|-------|------|--------|
| Orchestrator | Parallel triage + Guardian gate, calls Planner, builds execution workflow | ✅ Operational |
| Planner | Task decomposition with steps, dependency resolution, model recommendation | ✅ Operational |
| Builder | Creates ephemeral containers via Docker SDK, injects tools and agent cards | ✅ Operational *(beta)* |
| Guardian | OPA policy validation, risk scoring, prompt injection detection, emergency shutdown | ✅ Operational |
| Zombie (ephemeral) | Executes tasks with library tools, uploads artifacts, self-deregisters on completion | ✅ Operational *(beta)* |

### Infrastructure

| Component | What it does |
|-----------|-------------|
| Semantic Layer | Weaviate + MCP server — agent and tool discovery via embedding similarity |
| CLI | `abi-core create swarm`, `add agent`, `run` with auto TUI detection |
| TUI Console | Interactive Textual dashboard — services, logs, chat with orchestrator |
| MinIO | Artifact storage for ephemeral agent outputs |
| OPA | Policy engine with immutable core policies |
| Ollama | Local LLM serving — no API keys, no data leaves your network |
| Docker | Container lifecycle for ephemeral agents with auto-cleanup |

## 🏗️ Architecture

```
                              ┌─────────────┐
                              │    User     │
                              │  CLI / TUI  │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                         ┌───►│ Orchestrator │◄───┐
                         │    │  triage +    │    │
                         │    │  gate logic  │    │
                         │    └──┬───────┬───┘    │
                         │       │       │        │
                  ┌──────▼──┐ ┌──▼────┐ ┌▼───────────┐
                  │Guardian │ │Planner│ │   Builder   │
                  │OPA gate │ │decomp │ │Docker spawn │
                  └─────────┘ └───────┘ └──────┬──────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │  Zombie (ephemeral) │
                                    │  execute → artifact │
                                    │  → self-deregister  │
                                    └──────────┬──────────┘
                                               │
         ┌─────────────────────────────────────┼──────────────────┐
         │                                     │                  │
  ┌──────▼──────┐                     ┌────────▼───────┐  ┌──────▼──────┐
  │   Weaviate  │                     │     MinIO      │  │     OPA     │
  │  + MCP      │                     │   artifacts    │  │  policies   │
  │  semantic   │                     └────────────────┘  └─────────────┘
  │  discovery  │
  └─────────────┘
```

### Monorepo Structure

```
packages/
  abi-core/       — Runtime library: agent, semantic, security, tui, common
  abi-agents/     — Agent implementations: orchestrator, planner, builder, zombie
  abi-services/   — Service templates: semantic layer, guardian (Jinja2)
  abi-cli/        — CLI commands + project scaffolding
abi-image/        — Docker base image for agents and ephemeral containers
.abi/             — Project metadata, specs, session logs
```

## 🛠️ Technology Stack

| Category | Technologies |
|----------|-------------|
| Runtime | Python 3.11+, FastAPI, uvicorn |
| AI / LLM | LangChain, LangGraph, Ollama (local inference) |
| Protocols | MCP (Model Context Protocol), A2A SDK (Agent-to-Agent), HMAC signing |
| Semantic | Weaviate (vector DB), embedding similarity search |
| Security | OPA (Open Policy Agent), Guardian agent, immutable audit logs |
| Containers | Docker, Docker SDK (ephemeral lifecycle), Docker Compose |
| Storage | MinIO (artifacts via boto3) |
| CLI | Click, Rich, Jinja2 (scaffolding templates) |
| TUI | Textual (interactive dashboard) |
| Graphs | NetworkX (workflow orchestration) |

## 🚀 Quick Start

### Install
```bash
pip install abi-core-ai
```

### Create a Swarm *(beta)*
```bash
abi-core create swarm --name "my-swarm"
cd my-swarm
abi-core run
```

This generates a complete project with orchestrator, planner, builder, guardian, semantic layer, Weaviate, MinIO, OPA, Ollama — all wired up in Docker Compose. `abi-core run` starts everything and launches the interactive TUI.

### Build an Agent with `@agent.step`

Every ABI agent follows the same structure. You can scaffold it with the CLI or create it manually:

```
my-agent/
  config/
    __init__.py
    config.py       # Agent identity, LLM config, agent card
  agent.py          # Agent class extending AbiAgent
  main.py           # @agent.step() decorators + AbiCore().run()
```

**config/config.py** — Agent identity and LLM settings:
```python
import os
from a2a.types import AgentCard

class MyAgentConfig:
    AGENT_NAME = os.getenv("AGENT_NAME", "my-agent")
    AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_CONFIG = {
        "provider": "ollama",
        "model": MODEL_NAME,
        "temperature": 0.1,
        "base_url": OLLAMA_HOST,
    }

config = MyAgentConfig()

AGENT_CARD = AgentCard(**{
    "name": config.AGENT_NAME,
    "description": "My custom ABI agent",
    "url": f"http://{config.AGENT_NAME}:{config.AGENT_PORT}",
    "version": "1.0.0",
    "capabilities": {"streaming": "True"},
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [{"id": "process", "name": "Process", "description": "Process queries", "tags": ["general"]}],
})
```

**agent.py** — Agent class:
```python
from abi_core.agent.agent import AbiAgent
from config import config

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description="My custom ABI agent",
            llm_config=config.LLM_CONFIG,
            tools=[],
            system_prompt="You are a helpful agent.",
        )
```

**main.py** — DAG pipeline with `@agent.step()`:
```python
from abi_core.agent import AbiCore
from agent import MyAgent

agent = AbiCore()

@agent.step(
    name="gather_context",
    input_map={"query": "$input.query"},
)
async def gather_context(query):
    """Fetch relevant context for the query."""
    return {"context": f"Context for: {query}"}

@agent.step(
    name="execute",
    depends_on=["gather_context"],
    input_map={"context": "$gather_context", "query": "$input.query"},
)
async def execute(context, query):
    """Execute the task using gathered context."""
    return {"result": f"Executed: {query}"}

@agent.step(
    name="report",
    depends_on=["execute"],
    input_map={"result": "$execute"},
)
async def report(result):
    """Synthesize and return the final result."""
    return {"summary": result}

agent.run(MyAgent())
```

Three decorator types:
- `@agent.step()` — Deterministic DAG step. Runs in strict topological order.
- `@agent.tool()` — DAG step + LangChain tool. The LLM can also invoke it on demand.
- `@agent.mcp_tool()` — Remote MCP tool called via MCPToolkit with HMAC auth. No local function needed.

### Send a Query
```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Create a script that prints hello world", "context_id": "session-1"}'
```

## 📋 Agent Capabilities

### Orchestrator
Parallel triage (simple vs complex) + Guardian security gate. Discovers agents via MCP `find_agent` semantic search. Builds execution workflows with `AgentInteractionFlow` — dependency-aware, multi-step, with ephemeral agent support. SSE streaming via `/stream` endpoint.

DAG: `classify_query | guardian_validate` → `gate_decision` → `call_planner` → `extract_plan` → `build_workflow`

### Planner
LLM-based query decomposition into structured plans. Each task includes description, steps, dependencies, tools needed, and model recommendation. Assigns agents via semantic search — if no agent exists, marks task for `build_and_execute` (Builder handles it).

DAG: `analyze_query` → `parse_plan` → `assign_agents`

### Builder *(beta)*
Receives a builder spec, resolves required tools from the semantic layer, generates ephemeral agent config (Dockerfile, agent card, tool list), spawns a Docker container with injected environment, and registers the ephemeral agent card in Weaviate. Returns the agent card so the Orchestrator can route tasks to it.

DAG: `parse_spec` → `verify_tools` → `generate_config` → `build_container` → `register_card`

### Guardian
OPA policy validation for every request. Detects prompt injection, reverse engineering attempts, and policy violations. Returns risk scores with contextual modifiers. Immutable core policies auto-generated at startup — agents cannot modify them. Emergency shutdown always available.

### Zombie (Ephemeral) *(beta)*
Short-lived execution agent spawned by the Builder. Gathers context, executes tasks using injected library tools (`write_file`, `read_file`, `list_files`, `execute_command`), uploads artifacts to MinIO, then self-deregisters from Weaviate via `self_deregister_ephemeral` MCP tool and exits the container.

DAG: `gather_context` → `analyze_and_execute` → `synthesize_and_report`

## 🔧 Configuration

### Environment Variables
```bash
# Agent identity
AGENT_NAME=my-agent
AGENT_PORT=8001
ABI_ROLE=my-agent

# LLM
MODEL_NAME=qwen2.5:3b
OLLAMA_HOST=http://my-swarm-ollama:11434
LLM_PROVIDER=ollama

# Semantic layer
SEMANTIC_LAYER_HOST=http://my-swarm-semantic-layer:10100

# Security
A2A_VALIDATION_MODE=strict    # strict | permissive | disabled
GUARDIAN_URL=http://my-swarm-guardian:11438

# Ephemeral agents (injected by Builder)
AGENT_CARD_JSON='{"name":"ephemeral-task-1",...}'
LIBRARY_TOOLS='["write_file","read_file","execute_command"]'
TOOLS='["search_tool_registry"]'
```

### runtime.yaml
Generated by `abi-core create` in `.abi/runtime.yaml`:
```yaml
project:
  name: "my-swarm"
  version: "1.0.0"
  model_serving: "centralized"
  default_model: "qwen2.5:3b"

agents:
  orchestrator:
    name: "Orchestrator"
    port: 8000
  planner:
    name: "Planner"
    port: 8001
  builder:
    name: "Builder"
    port: 8002

services:
  semantic_layer:
    type: "semantic-layer"
    port: 10100
  guardian:
    type: "guardian"
    port: 11438
  weaviate:
    type: "weaviate"
    port: 8080

interface:
  type: "tui"
  entry: "console.py"
  enabled: true
```

---

## 🔒 Security & Governance

### How Security Works in the Pipeline

Every query passes through the Guardian before execution:

1. **Orchestrator** runs `classify_query` and `guardian_validate` in parallel
2. **Guardian** checks against OPA policies: prompt injection, reverse engineering, policy compliance
3. **Gate decision** merges results — blocks, allows, or returns error
4. Only approved queries proceed to the Planner

### OPA Policy Engine
- Immutable core policies auto-generated at startup — agents cannot modify them
- Multi-layer evaluation: core policies + custom project policies
- Risk scoring with contextual modifiers
- Fail-safe defaults: deny by default

### Agent-to-Agent Security
- All A2A communication validated via OPA `a2a_access.rego`
- HMAC signing for MCP tool calls between agents
- Agent cards carry identity — semantic layer validates on every request
- Ephemeral agents use `self_deregister_ephemeral` (dedicated MCP tool) to avoid OPA blocks on cleanup

### Governance Rules (Enforced by OPA)
- Self-replication strictly prohibited
- Policy modification blocked for all agents
- System-level access denied
- Network access controlled to authorized endpoints
- Resource access validated with risk assessment
- Immutable audit logs for every decision

## 📚 Documentation

- [Architecture Overview](abi_core_framework/docs/architecture.md)
- [Agent Protocols](abi_core_framework/docs/agent_protocols.md)
- [Environment Variables](abi_core_framework/docs/ENVIRONMENT_VARIABLES.md)
- [Session Management](abi_core_framework/docs/SESSION_MANAGEMENT.md)
- [Manifesto](MANIFIESTO.md)
- [Whitepaper](WHITEPAPER.md)
- [PyPI Documentation](https://abi-core.readthedocs.io)

---

## 🤝 Contributing

ABI is an open-source project. Contributions welcome in any area:

- Agent implementations and tools
- Semantic layer improvements
- Security policies and governance
- CLI and TUI enhancements
- Documentation and examples

```bash
git clone https://github.com/Joselo-zn/abi-core
cd abi-core
pip install -e ".[dev]"
pytest
```

---

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE).

Read the [Manifesto](MANIFIESTO.md) and [Whitepaper](WHITEPAPER.md) for the philosophical foundations.

---

## Status

The E2E pipeline is functional and verified. The system receives natural language instructions, decomposes them into plans, spawns ephemeral agents in Docker containers, executes with injected tools, uploads artifacts, and cleans up automatically.

### Roadmap

| Phase | What | Status |
|-------|------|--------|
| 1. Foundations | Interactive CLI/TUI, Plan Confirmation, Docker auto-cleanup | 🔧 In progress |
| 2. Intelligence | Result Validation, Plan Learning, Orchestrator Synthesis Refactor | 🔜 Next |
| 3. Capabilities | Model Management, Artifact Transport, Hybrid Tool Discovery | 📋 Planned |
| 4. Knowledge | Swarm Knowledge Base (.abi/ as MCP tools) | 📋 Planned |
| — | Production stable release | 🏁 Target 2026 |

---

## ✨ From Curiosity to Creation: A Personal Note
I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated. At the time, I wanted to study robotics — but when I touched that machine, everything changed. I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big. When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying. Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI. This is for the kids like me, then and now.

## About the Author

**José Luis Martínez** is a systems engineer, AI infrastructure strategist, and creator of the ABI (Agent-Based Infrastructure) paradigm.  
This project is part of an ongoing research effort to democratize intelligent systems and create shared cognition frameworks for open innovation.

Connect on [LinkedIn](https://www.linkedin.com/in/jose-luis-martinez-71195425/) | [Blog](https://designednotmagic.hashnode.dev)