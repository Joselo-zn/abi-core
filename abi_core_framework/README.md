# ABI-Core 🤖  
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

## 🚀 Quick Start

### Installation
```bash
pip install abi-core-ai
```

### Create Your First Project
```bash
# Create a new ABI project with semantic layer
abi-core create project my-ai-system --with-semantic-layer

# Navigate to your project
cd my-ai-system

# Provision models (automatically starts services and downloads models)
abi-core provision-models

# Create an agent (includes interactive skills session + automatic agent card creation)
abi-core add agent my-agent --description "My first AI agent"

# Run your project
abi-core run
```

> 📖 **Need help?** Check out our [complete documentation](https://abi-core.readthedocs.io) with guides, examples, and API reference.

---

## 🆕 What's New in v1.2.0

### 🏗️ Modular Architecture
ABI-Core now uses a **modular monorepo structure** for better maintainability and community collaboration:

```
packages/
├── abi-core/          # Core libraries (common/, security/, opa/, abi_mcp/)
├── abi-agents/        # Agent implementations (orchestrator/, planner/)  
├── abi-services/      # Services (semantic-layer/, guardian/)
├── abi-cli/           # CLI and scaffolding tools
└── abi-framework/     # Umbrella package with unified API
```

**Benefits:**
- ✅ **Backward Compatible** — All existing imports continue to work
- ✅ **Modular Development** — Each package can be developed independently
- ✅ **Community Friendly** — Easier to contribute to specific components
- ✅ **Deployment Flexibility** — Deploy only the components you need

### 🌐 Enhanced Open WebUI Compatibility
- ✅ **Fixed Connection Issues** — Resolved `Unclosed client session` errors
- ✅ **Improved Streaming** — Better real-time response handling
- ✅ **Proper Headers** — Correct CORS and connection management
- ✅ **Template Consistency** — Synchronized web interfaces across all agents

## 🔧 Model Serving Options

ABI-Core supports two model serving strategies for Ollama:

### Centralized (Recommended for Production)
A single shared Ollama service serves all agents:
- ✅ **Lower resource usage** — One Ollama instance for all agents
- ✅ **Easier model management** — Centralized model updates
- ✅ **Faster agent startup** — No need to start individual Ollama instances
- ✅ **Centralized caching** — Shared model cache across agents

```bash
abi-core create project my-app --model-serving centralized
```

### Distributed (Default)
Each agent has its own Ollama instance:
- ✅ **Complete isolation** — Each agent has independent models
- ✅ **Independent versions** — Different model versions per agent
- ✅ **Development friendly** — Easy to test different configurations
- ⚠️ **Higher resource usage** — Multiple Ollama instances

```bash
abi-core create project my-app --model-serving distributed
# or simply (distributed is default)
abi-core create project my-app
```

**Note:** Guardian service always maintains its own Ollama instance for security isolation, regardless of the chosen mode.

---

## 🎯 What is ABI-Core?

ABI-Core-AI is a production-ready framework for building **Agent-Based Infrastructure** systems that combine:

- **🤖 AI Agents** — LangChain-powered agents with A2A (Agent-to-Agent) communication  
- **🧠 Semantic Layer** — Vector embeddings and distributed knowledge management  
- **🔒 Security** — OPA-based policy enforcement and access control  
- **🌐 Web Interfaces** — FastAPI-based REST APIs and real-time dashboards  
- **📦 Containerization** — Docker-ready deployments with orchestration  

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Agents     │◄──►│ Semantic Layer  │◄──►│   Guardian      │
│                 │    │                 │    │   Security      │
│ • LangChain     │    │ • Vector DB     │    │ • OPA Policies  │
│ • A2A Protocol  │    │ • Embeddings    │    │ • Access Control│
│ • Custom Logic  │    │ • Knowledge     │    │ • Monitoring    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Web Interface  │
                    │                 │
                    │ • FastAPI       │
                    │ • Real-time UI  │
                    │ • Monitoring    │
                    └─────────────────┘
```

---

## 📋 Features

### 🤖 Agent System
- **Multi-Agent Architecture** — Create specialized agents for different tasks  
- **A2A Communication** — Agents can communicate and collaborate with automatic security validation
- **LangChain Integration** — Leverage the full LangChain ecosystem  
- **Custom Tools** — Extend agents with domain-specific capabilities  
- **Workflow System** — LangGraph-based workflow orchestration with built-in A2A validation
- **Centralized Config** — All agents have config/ directory for type-safe configuration  

### 🧠 Semantic Layer
- **Agent Discovery** — MCP-based agent finding and routing  
- **Vector Storage** — Weaviate-based semantic search (automatically configured)
- **Agent Cards** — Structured agent metadata and capabilities  
- **Access Validation** — OPA-integrated security for semantic access with user validation
- **Embedding Mesh** — Distributed embedding computation and caching  
- **Context Awareness** — Agents understand semantic relationships  
- **Auto-Configuration** — Weaviate vector database included automatically
- **MCP Toolkit** — Dynamic access to custom MCP tools with pythonic syntax  

### 🔒 Security & Governance
- **Policy Engine** — Open Policy Agent (OPA) integration  
- **Access Control** — Fine-grained permissions and roles  
- **A2A Validation** — Agent-to-Agent communication security with automatic validation
- **User Validation** — User-level access control for semantic layer  
- **Audit Logging** — Complete activity tracking with user and agent context
- **Compliance** — Built-in security best practices  
- **Centralized Configuration** — Type-safe config management for all services  

### 🌐 Web & APIs
- **REST APIs** — FastAPI-based service endpoints  
- **Real-time Updates** — WebSocket support for live data  
- **Admin Dashboard** — Monitor and manage your agent system  
- **Custom UIs** — Build domain-specific interfaces  

---

## 🛠️ CLI Commands

### Project Management
```bash
# Create new projects with optional services and model serving strategy
abi-core create project <name> [--domain <domain>] [--with-semantic-layer] [--with-guardian] [--model-serving centralized|distributed]
abi-core provision-models          # Download and configure LLM models (auto-starts services)
abi-core status                    # Check project status
abi-core run                       # Start all services
abi-core info                      # Show project information
```

### Agent Development
```bash
# Create and manage agents (includes interactive skills session + automatic agent card)
abi-core add agent <name> [--description <desc>] [--model <model>] [--with-web-interface]
abi-core remove agent <name>       # Remove an agent
abi-core info agents               # List all agents
```

### Services Management
```bash
# Add services to existing projects
abi-core add service semantic-layer [--name <name>] [--domain <domain>]
abi-core add service guardian [--name <name>] [--domain <domain>]
abi-core add service guardian-native [--name <name>] [--domain <domain>]

# Quick service shortcuts
abi-core add semantic-layer [--domain <domain>]    # Add semantic layer directly
abi-core remove service <name>                     # Remove any service
```

### Agent Cards & Semantic Layer
```bash
# Agent cards are created automatically with 'add agent'
# Use 'add agent-card' only for manual/custom card creation
abi-core add agent-card <name> [--description <desc>] [--model <model>] [--url <url>] [--tasks <tasks>]
abi-core add policies <name> [--domain <domain>]   # Add security policies
```

### Examples
```bash
# Create a finance project with centralized model serving (recommended for production)
abi-core create project fintech-ai --domain finance --with-semantic-layer --with-guardian --model-serving centralized
cd fintech-ai

# Provision models (starts Ollama and downloads qwen2.5:3b + embeddings)
abi-core provision-models

# Add a specialized trading agent (automatically uses centralized Ollama)
# → Interactive session will prompt for skills and agent URL
abi-core add agent trader --description "AI trading assistant" --model qwen2.5:3b

# Agent card is created automatically during 'add agent'
# Use 'add agent-card' only if you need a custom card later:
# abi-core add agent-card trader --description "Execute trading operations" --url http://localhost:8001 --tasks "trade,analyze,risk-assessment"

# Add semantic layer to existing project (Weaviate included automatically)
abi-core add semantic-layer --domain finance

# Create a development project with distributed model serving (each agent has own Ollama)
abi-core create project dev-project --model-serving distributed
cd dev-project

# Provision models (starts all agents with their Ollama instances + main Ollama for embeddings)
abi-core provision-models

# Remove components when needed
abi-core remove service semantic_layer
abi-core remove agent trader
```

---

## 📁 Project Structure

When you create a new project, you get:

```
my-project/
├── agents/                 # Your AI agents
│   └── my-agent/
│       ├── config/         # Centralized configuration (NEW)
│       │   ├── __init__.py
│       │   └── config.py   # Type-safe config with A2A settings
│       ├── agent.py        # Agent implementation
│       ├── main.py         # Entry point
│       ├── models.py       # Data models
│       └── agent_cards/    # Agent card (auto-created with 'add agent')
├── services/               # Supporting services
│   ├── web_api/            # Main web application
│   │   ├── config/         # Application configuration
│   │   ├── main.py         # FastAPI application
│   │   ├── Dockerfile      # Container configuration
│   │   └── requirements.txt
│   ├── semantic_layer/     # AI agent discovery & routing
│   │   ├── config/         # Semantic layer configuration (NEW)
│   │   └── layer/
│   │       ├── mcp_server/ # MCP server for agent communication
│   │       └── embedding_mesh/ # Vector embeddings & search
│   └── guardian/           # Security & policy enforcement
│       ├── config/         # Guardian configuration (NEW)
│       ├── agent/          # Guardian agent code
│       └── opa/            # OPA policies
│           └── policies/
│               ├── semantic_access.rego
│               └── a2a_access.rego  # A2A validation policy (NEW)
├── compose.yaml            # Container orchestration
├── .abi/                   # ABI project metadata
│   └── runtime.yaml
└── README.md               # Project documentation
```

---

## �  Security Features

### A2A Validation (Agent-to-Agent)
Automatic security validation for all agent communications:

```python
from config import AGENT_CARD
from abi_core.common.workflow import WorkflowGraph

# Create workflow
workflow = WorkflowGraph()
# ... add nodes ...

# Set source card for automatic A2A validation
workflow.set_source_card(AGENT_CARD)

# All communications are now automatically validated!
async for chunk in workflow.run_workflow():
    process(chunk)
```

**Features:**
- ✅ Automatic validation before each communication
- ✅ OPA policy-based access control
- ✅ Three modes: strict (production), permissive (dev), disabled (testing)
- ✅ Complete audit logging
- ✅ Configurable communication rules

### User Validation
User-level access control for semantic layer operations:

```python
from abi_core.security.agent_auth import with_agent_context

context = with_agent_context(
    agent_id="my-agent",
    tool_name="find_agent",
    mcp_method="callTool",
    user_email="user@example.com",  # User validation
    query="search query"
)
```

**Configuration:**
```bash
# Environment variables
A2A_VALIDATION_MODE=strict          # strict, permissive, or disabled
A2A_ENABLE_AUDIT_LOG=true
GUARDIAN_URL=http://guardian:8383
```

---

## 🔧 Configuration

ABI-Core uses environment variables and YAML configuration files:

```yaml
# .abi/runtime.yaml
agents:
  my-agent:
    model: "qwen2.5:3b"
    port: 8000
    
semantic_layer:
  provider: "weaviate"
  host: "localhost:8080"
  
security:
  opa_enabled: true
  policies_path: "./policies"
```

---

## 🚀 Deployment

### Docker (Recommended)
```bash
docker-compose up --build
docker-compose up --scale my-agent=3
```

### Kubernetes
```bash
abi-core-ai deploy kubernetes
kubectl apply -f ./k8s/
```

---

## 🧪 Examples

### Simple Agent
```python
from abi_core.agent.agent import AbiAgent
from abi_core.common.utils import abi_logging

class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='my-agent',
            description='A helpful AI assistant'
        )
    
    async def stream(self, query: str, context_id: str, task_id: str):
        abi_logging(f"Processing: {query}")
        response = await self.llm.ainvoke(query)
        yield {
            'content': response.content,
            'response_type': 'text',
            'is_task_completed': True
        }
```

### Agent Communication
```python
await self.send_message(
    target_agent="agent-b",
    message="Process this data",
    data={"items": [1, 2, 3]}
)
```

---

## 📚 Documentation

**📖 Full Documentation:** [https://abi-core.readthedocs.io](https://abi-core.readthedocs.io)

- **[Getting Started](https://abi-core.readthedocs.io/en/latest/getting-started/installation.html)** - Installation and quick start
- **[Quick Start Guide](https://abi-core.readthedocs.io/en/latest/getting-started/quickstart.html)** - Get running in 5 minutes
- **[Models Guide](https://abi-core.readthedocs.io/en/latest/user-guide/models.html)** - Model selection and provisioning
- **[FAQ](https://abi-core.readthedocs.io/en/latest/faq.html)** - Frequently asked questions
- **[Architecture](https://abi-core.readthedocs.io/en/latest/architecture.html)** - System design and concepts  

---

## 🤝 Contributing

We welcome contributions! This is a beta release, so your feedback is especially valuable.

### Development Setup
```bash
git clone https://github.com/Joselo-zn/abi-core
cd abi-core-ai
uv sync --dev
```

### Running Tests
```bash
uv run pytest
```

---

## 📄 License

Apache 2.0 License — see [LICENSE](LICENSE) for details.

---

## 🆘 Support

- **Issues** — [GitHub Issues](https://github.com/Joselo-zn/abi-core/issues)  
- **Discussions** — [GitHub Discussions](https://github.com/Joselo-zn/abi-core/issues/discussions)  
- **Email** — jl.mrtz@gmail.com  

---

## 🗺️ Roadmap

| Milestone | Description | Status |
|------------|--------------|--------|
| v0.2.0 | Enhanced agent orchestration | 🔜 In progress |
| v0.3.0 | Advanced semantic search | 🧠 Planned |
| v0.4.0 | Multi-cloud deployment | 🧩 Planned |
| v1.0.0 | Production-ready stable release | 🏁 Target Q3 2026 |

---

**Built with ❤️ by [José Luis Martínez](https://github.com/Joselo-zn)**  
Creator of **ABI (Agent-Based Infrastructure)** — redefining how intelligent systems interconnect.

✨ From Curiosity to Creation: A Personal Note

I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated.
At the time, I wanted to study robotics — but when I touched that machine, everything changed.

I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big.
When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying.

Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI.
This is for the kids like me, then and now.