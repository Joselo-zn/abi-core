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
| Agent lifecycle | Ephemeral containers — spawn, execute, self-destruct | Long-running processes |
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

### 2. Ephemeral by Design
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
| Builder | Creates ephemeral containers via Docker SDK, injects tools and agent cards | ✅ Operational |
| Guardian | OPA policy validation, risk scoring, prompt injection detection, emergency shutdown | ✅ Operational |
| Zombie (ephemeral) | Executes tasks with library tools, uploads artifacts, self-deregisters on completion | ✅ Operational |

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

### Prerequisites
- Docker and Docker Compose
- 8GB+ RAM recommended
- NVIDIA GPU (optional, for faster inference)

### Launch the System
```bash
cd abi-core
docker-compose up -d
```

### Access Points
- **Orchestrator API**: http://localhost:8082 (workflow coordination)
- **Actor Agent API**: http://localhost:8083 (task execution)
- **Guardian Agent API**: http://localhost:8003 (policy validation)
- **Semantic Layer MCP**: http://localhost:10100 (agent discovery)
- **Weaviate Console**: http://localhost:8080 (vector database)
- **OPA Policy Server**: http://localhost:8181 (policy engine)

### Example Usage
```bash
# Send a query to the orchestrator
curl -X POST http://localhost:8082/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze the latest market trends and create a summary report",
    "context_id": "user-session-123",
    "task_id": "task-001"
  }'
```

## 📋 Agent Capabilities

### Orchestrator Agent ✅
- **Workflow coordination** using NetworkX graphs with pause/resume
- **Semantic agent discovery** via MCP server integration (`find_agent` tool)
- **Real-time streaming** with A2A protocol communication
- **Context preservation** across multi-step workflows
- **Human-in-the-loop** decision points with automatic Q&A

### Planner Agent ✅
- **Query decomposition** using LangGraph with structured responses
- **Task sequencing** with dependency resolution
- **Memory persistence** via LangGraph checkpointer
- **A2A communication** for inter-agent coordination

### Actor Agent ✅
- **Task execution** with LangChain integration
- **A2A communication** for inter-agent coordination
- **Structured result reporting** with artifact generation
- **Error handling** and recovery mechanisms

### Guardian Agent ✅
- **Advanced OPA integration** with secure policy engine
- **Immutable core policies** that cannot be overridden by agents
- **Real-time policy validation** with risk scoring
- **Emergency shutdown** mechanisms always available
- **Comprehensive audit trails** with remediation suggestions
- **Dashboard and alerting** system integration

### Observer Agent 🚧
- **System monitoring** (architecture defined, implementation pending)
- **Performance metrics** collection and analysis
- **Anomaly detection** and alerting
- **Health checks** and diagnostics

## 🔧 Configuration

### Environment Variables
```bash
# LLM Configuration
MODEL_NAME=llama3.2:3b
OLLAMA_HOST=http://abi-llm-base:11434

# Database Configuration
WEAVIATE_URL=http://abi-weaviate:8080
SQLLITE_DB=abi_context.db

# Agent Configuration
ABI_ROLE=Agent_Name
ABI_NODE=ABI_Node
PYTHONPATH=/app
```

### Agent Cards
Each agent is defined by a JSON configuration card specifying:
- Capabilities and skills
- Input/output modes
- Communication protocols
- Metadata and requirements

## 🔒 Security & Governance

### Advanced OPA Policy Engine ✅
- **Immutable core policies** auto-generated at startup
- **Multi-layer policy evaluation** (core + custom policies)
- **Real-time risk scoring** with contextual modifiers
- **Fail-safe security defaults** (deny by default)
- **Comprehensive audit logging** with decision traceability

### Built-in Safety Mechanisms
- **Human veto power** on all critical decisions (implemented)
- **Emergency shutdown** mechanisms always available
- **Self-replication blocking** via core policies
- **Policy modification protection** (agents cannot alter security policies)
- **Sensitive data detection** and blocking

### Governance Rules (Enforced by OPA)
- ✅ **Self-replication strictly prohibited** by immutable core policies
- ✅ **Policy modification blocked** for all agents except human operators
- ✅ **System-level access denied** to all agents
- ✅ **Network access controlled** to authorized endpoints only
- ✅ **Resource access validated** with risk assessment

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [Agent Protocols](docs/agent_protocols.md)
- [Governance Framework](docs/gobernance.md)
- [Core Stack Details](CORE-STACK.md)
- [Infrastructure Guide](INFRA-STACK.md)
- [Development Roadmap](ROADMAP.md)

## 🤝 Contributing

ABI is an open-source project welcoming contributions from the community. Whether you're interested in:

- Enhancing existing agent capabilities
- Implementing the Observer agent
- Improving the semantic layer
- Expanding security mechanisms
- Adding tool integrations
- Writing documentation

Please see our contribution guidelines and join the discussion.

## 📄 License & Philosophy

Distributed under the [Apache License 2.0](LICENSE).

Read our [Manifesto](MANIFIESTO.md) and [Whitepaper](WHITEPAPER.md) to understand the philosophical foundations of ABI.

## Status

**ABI is a functional MVP demonstrating distributed agent-based infrastructure** with semantic discovery and human supervision.  
The system provides a solid foundation with 4/5 agents operational, OPA policy engine, and MCP-based semantic workflow orchestration. This MVP serves as an extensible platform for building production-ready multi-agent systems.

### Current Implementation Status:
- **Infrastructure**: ✅ Production-ready (Docker, Weaviate, Ollama, MCP Server)
- **Core Agents**: ✅ Operational with A2A communication and semantic discovery
- **Security Layer**: ✅ Advanced Guardian with OPA integration and emergency systems
- **Semantic Layer**: ✅ MCP-based agent discovery with embedding similarity
- **Observer Agent**: 🚧 Framework ready, implementation pending

### Key Architectural Achievements:
- **Semantic Agent Discovery**: Agents discover each other via MCP `find_agent` tool using embedding similarity
- **A2A Communication**: All agents implement A2A server with standardized communication protocol
- **Human Supervision**: Native human-in-the-loop controls with emergency shutdown capabilities
- **Policy-First Security**: OPA-based governance with immutable core policies
- **Vendor Independence**: Local LLM execution with Ollama, no external API dependencies

### Roadmap to Production:
1. **Complete Observer Agent** - Implement monitoring and metrics collection
2. **Enhanced Tool Ecosystem** - Expand agent capabilities with specialized tools
3. **Performance Optimization** - Optimize semantic discovery and A2A communication
4. **Enterprise Features** - Multi-tenancy, advanced security, and compliance
5. **Community Ecosystem** - Agent marketplace and contribution framework

---

## ✨ From Curiosity to Creation: A Personal Note
I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated. At the time, I wanted to study robotics — but when I touched that machine, everything changed. I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big. When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying. Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI. This is for the kids like me, then and now.

## About the Author

**José Luis Martínez** is a systems engineer, AI infrastructure strategist, and creator of the ABI (Agent-Based Infrastructure) paradigm.  
This project is part of an ongoing research effort to democratize intelligent systems and create shared cognition frameworks for open innovation.

Connect on [LinkedIn](https://www.linkedin.com/in/jose-luis-martinez-71195425/) | [Blog](https://designednotmagic.hashnode.dev)