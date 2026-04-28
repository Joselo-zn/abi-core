# ABI Swarm 🤖
[![PyPI version](https://badge.fury.io/py/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![Python](https://img.shields.io/pypi/pyversions/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![License](https://img.shields.io/pypi/l/abi-core-ai.svg)](https://github.com/Joselo-zn/abi-core-ai/blob/main/LICENSE)
[![Documentation](https://readthedocs.org/projects/abi-core/badge/?version=latest)](https://abi-core.readthedocs.io/en/latest/?badge=latest)

**ABI-Core-AI** — The open-source framework for building **Agent-Based Infrastructure (ABI)** — distributed, self-building multi-agent systems where agents collaborate through semantic context, execute tasks in ephemeral containers, and operate under policy-driven governance.

ABI-Core provides the runtime, CLI, and building blocks to create, deploy, and operate multi-agent swarms from a single `pip install`. It handles orchestration, planning, ephemeral agent lifecycle, semantic discovery, security validation, and artifact management — so you can focus on what your agents do, not how they connect.

> 🎉 **v1.9+ Released!** — Full E2E pipeline: orchestrator → planner → builder → ephemeral agents → artifacts. Interactive TUI console. Self-building swarm with `abi-core create swarm`.

---

## 🧭 Why ABI?

Most agent frameworks solve the same problem: how to wire an LLM to tools. ABI solves a different one: how to build a system where multiple agents collaborate, self-organize, and operate under governance — without depending on a single vendor, a single model, or a centralized API.

| | ABI-Core | LangGraph / CrewAI / AutoGen |
|---|---|---|
| Architecture | Distributed swarm with semantic discovery | Centralized graph or crew definition |
| Agent lifecycle | Ephemeral containers — spawn, execute, self-destruct | Long-running processes |
| Tool discovery | Semantic layer (Weaviate) — agents find each other by meaning | Hardcoded tool lists or registries |
| Security | OPA policies + Guardian agent + HMAC per request | Varies, usually app-level |
| Model serving | Local-first (Ollama), vendor-agnostic | Typically API-dependent (OpenAI, etc.) |
| Scaffolding | Full CLI: `abi-core create swarm` generates everything | Manual setup or minimal templates |
| Governance | Built-in: audit logs, human veto, policy engine | Not included |
| Target | Universities, NGOs, labs, open-source communities | Developers building single-purpose agents |

ABI is not just a framework — it's an infrastructure paradigm. The agents don't just call tools; they discover each other semantically, negotiate execution plans, spawn ephemeral workers in containers, upload artifacts, and clean up after themselves. All auditable, all governed, all local-first.

### Core Principles

1. **Semantic Interoperability** — Agents share meaning through vector embeddings, not hardcoded routes.
2. **Distributed Intelligence** — No single model owns the truth. Orchestrator plans, planner decomposes, builder spawns, ephemeral executes.
3. **Governed Autonomy** — Every action passes through OPA policies and Guardian validation. Humans retain veto power at all times.
4. **Local-First** — Runs on your hardware with Ollama. No API keys required. No data leaves your network.

> ⚠️ **Beta Release**: APIs may change. Some features are experimental. The pipeline is functional end-to-end.

---

## Quick Start

```bash
pip install abi-core-ai

# Create a complete swarm (project + all agents + services)
abi-core create swarm --name my-swarm

# Or step by step:
abi-core create project my-system --with-semantic-layer --with-guardian
abi-core add abi-swarm

# Run
abi-core run              # Detached (banner + status only)
abi-core run --logs       # With container logs
abi-core run --build      # Rebuild containers first
```

---

## Architecture

```
User Request
     │
     ▼
┌──────────────────────────────────────────────────┐
│                  Orchestrator                     │
│                                                   │
│  ┌─────────────┐  ┌──────────────────┐           │
│  │  Triage     │  │  Guardian Gate   │  Level 0  │
│  │  (simple/   │  │  (security       │  parallel │
│  │   complex)  │  │   validation)    │           │
│  └──────┬──────┘  └────────┬─────────┘           │
│         └────────┬─────────┘                      │
│                  ▼                                 │
│         ┌────────────────┐                        │
│         │ Gate Decision  │  Level 1               │
│         │ approve/block/ │  merge                 │
│         │ respond/plan   │                        │
│         └───────┬────────┘                        │
│                 │                                  │
│    ┌────────────┴────────────┐                    │
│    ▼                         ▼                    │
│  Simple                   Complex                 │
│  → LLM responds           → Planner → Builder    │
│    directly                 → Execute → Synthesize│
└──────────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Semantic   │  │  Guardian   │  │   MinIO      │
│   Layer     │  │  Security   │  │  Artifacts   │
│             │  │             │  │              │
│ Agent Cards │  │ OPA Policies│  │ Code, Data   │
│ Tool Cards  │  │ A2A Auth    │  │ Results      │
│ Service Cards│ │ Audit Log   │  │ S3-compat    │
│ MCP Tools   │  │ Risk Score  │  │              │
└─────────────┘  └─────────────┘  └──────────────┘
```

---

## Core Concepts

### AbiCore — FastAPI-style Agent Runner

```python
from abi_core.agent import AbiCore
from my_agent import MyAgent

agent = AbiCore()

@agent.task(name="step1")
def step1(raw_input):
    return {"cleaned": raw_input.strip()}

@agent.task(name="step2", depends_on=["step1"], input_map={"data": "$step1.result"})
def step2(data):
    return {"stored": True}

@agent.tool(name="search")
def search(query):
    """Available to the LLM on demand."""
    return {"results": []}

@agent.mcp_tool(name="bigquery_search", input_map={"query": "$input.user_query"})

agent.run(MyAgent())
```

### invoke() — Unified LLM Calls

```python
from abi_core.agent import invoke

# LLM only, no context
result = await invoke(config.LLM_CONFIG, "Classify this query...")

# LLM with conversation memory
result = await invoke(config.LLM_CONFIG, "Summarize...", thread_id=context_id)

# Agent with tools, no context
result = await invoke(config.LLM_CONFIG, "Find agent...", tools=[tool_find_agent])

# Agent with tools and memory
result = await invoke(config.LLM_CONFIG, query, tools=[find, search], thread_id=session_id)
```

### ToolExecutionGraph — Deterministic DAG with Parallelism

Tasks registered with `@agent.task()` are wired into a LangGraph DAG. Nodes at the same dependency level execute in parallel. The LLM never decides execution order — the graph does. Retry, checkpoint/resume, and `$reference` resolution between nodes are built in.

### Three Types of Cards

| Card | Purpose | Example |
|------|---------|---------|
| **AgentCard** | Identity for agents (permanent or ephemeral) | Planner, Builder, zombie agents |
| **ServiceCard** | Identity for non-agent services | Webapp, semantic layer |
| **ToolCard** | Metadata for MCP tools with access_scope | query_sales_db, send_email |

All cards support HMAC authentication, checksum verification, and OPA policy evaluation.

### Zombie Container Pattern

Ephemeral agents run a 3-phase DAG:
1. **gather_context** — Pull artifacts from MinIO, prepare workspace
2. **analyze_and_execute** — LLM autonomous with tools (decides what to call)
3. **synthesize_and_report** — Package results, upload artifacts

No `docker build` — just `docker run` with env vars. The zombie self-configures as a fully functional A2A agent.

---

## Features

- **AbiCore Runner** — `agent = AbiCore()` with auto-config import
- **Decorator API** — `@agent.task()`, `@agent.tool()`, `@agent.mcp_tool()`
- **ToolExecutionGraph** — LangGraph DAG with parallel execution and Annotated reducers
- **invoke()** — Unified LLM calls: LLM-only, agent+tools, with/without context
- **SSE Heartbeat** — Automatic keepalive for CloudFront/proxy compatibility
- **Session Management** — Auto process_answer(), clear_session(), _yield_clarification() in AbiAgent base
- **AgentResponse** — Typed responses: `.success()`, `.error()`, `.status()`, `.input_required()`
- **A2AResponse** — Streaming event parser for TaskArtifactUpdateEvent and TaskStatusUpdateEvent
- **Multi-Provider LLM** — Ollama, OpenAI, Anthropic, Bedrock, Azure, Vertex AI, Grok
- **MCP Protocol** — Streamable HTTP transport with auto-reconnection
- **MCPToolkit** — Dynamic tool calling with ServiceCard or AgentCard auth
- **Three Card Types** — AgentCard, ServiceCard, ToolCard with HMAC, checksum, access_scope
- **Guardian Gate** — Parallel triage + security validation before any agent executes
- **OPA Policies** — Support for agent://, service://, tool:// prefixes and ephemeral agents
- **Semantic Layer** — Weaviate vector search for agents, tools, and services
- **ArtifactStore** — S3-compatible object storage (MinIO local, AWS S3, GCS production)
- **ContainerRuntime** — Docker lifecycle abstraction (run, destroy, health check)
- **Builder** — Creates ephemeral agents with register/deregister lifecycle
- **Zombie Pattern** — 3-phase DAG: gather → execute (LLM autonomous) → report
- **Tree of Thoughts** — Planner and Orchestrator prompts with multi-path reasoning
- **Infrastructure Filter** — Prevents builder/planner/orchestrator from being assigned as task executors
- **CLI** — `abi-core create swarm`, `abi-core create project`, `abi-core add abi-swarm`, `abi-core run`

---

## CLI Commands

```bash
# Swarm (everything in one command)
abi-core create swarm --name <name>

# Project (step by step)
abi-core create project <name> [--with-semantic-layer] [--with-guardian]
abi-core add abi-swarm

# Run
abi-core run              # Detached (banner + status table)
abi-core run --logs       # With container logs
abi-core run --build      # Rebuild containers

# Agents
abi-core add agent <name> --description "..."
abi-core remove agent <name>

# Services
abi-core add semantic-layer
abi-core add service guardian-native
```

---

## Project Structure

```
my-swarm/
├── agents/
│   ├── planner/          # Task decomposition (Tree of Thoughts)
│   ├── orchestrator/     # Triage + Guardian gate + workflow coordination
│   ├── builder/          # Ephemeral agent creation + registration
│   └── my-agent/         # Your custom agents
├── services/
│   ├── web_api/          # FastAPI application + ServiceCard
│   │   └── service_cards/
│   ├── semantic_layer/   # MCP server + Weaviate
│   │   ├── agent_cards/
│   │   ├── tool_cards/
│   │   └── service_cards/
│   └── guardian/         # OPA security + audit
├── compose.yaml          # All services + MinIO + OPA
└── .abi/runtime.yaml
```

---

## Documentation

[https://abi-core.readthedocs.io](https://abi-core.readthedocs.io)

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

**Built by [José Luis Martínez](https://github.com/Joselo-zn)** — Creator of ABI (Agent-Based Infrastructure)
