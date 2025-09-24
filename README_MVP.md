# ABI – Agent-Based Infrastructure (MVP)
Created and maintained by José Luis Martínez

**ABI** is a paradigm shift in how we design, deploy, and interact with intelligent systems.

Instead of centralizing superintelligence behind APIs or monolithic LLMs, ABI implements a distributed, agent-based architecture where cognition is shared, decisions are explainable, and humans remain in control.

This repository contains a **functional MVP implementation** of ABI: a human-supervised, auditable infrastructure that enables universities, NGOs, independent labs, and open-source communities to access and build on top of intelligent, modular agents.

## Why ABI?

AI today is not just about performance — it's about control.  
ABI is designed to make intelligent infrastructure accessible, safe, and inspectable by default.

It's not just "agent-based tech."  
It's an architecture designed to reason, act, and learn across networks — and to be supervised by people, not just orchestrated by scripts.

## Core principles

- **Human-based supervision** over automation
- **Shared context** and semantic communication between agents
- **Layered architecture**: physical infra, semantic protocols, agent layer, governance
- **Explainability and auditability** by design
- **No black boxes** — cognition is distributed, not hidden

## 🚀 What's Implemented (MVP Status)

### Multi-Agent System
- **4 core agents** in MVP operational state + 1 framework ready:
  - **Orchestrator**: ✅ Basic workflow coordination with LangChain integration
  - **Planner**: ✅ Task decomposition using LangGraph (extensible foundation)
  - **Actor**: ✅ Basic task execution with structured responses
  - **Guardian**: ✅ OPA policy engine with emergency response capabilities
  - **Observer**: 🚧 Architecture defined, implementation framework ready

### Core Infrastructure
- **Docker-based deployment** with full containerization
- **Weaviate vector database** for semantic search and embeddings
- **Ollama integration** for local LLM execution with jina embeddings
- **FastAPI** REST APIs for each agent with A2A protocol foundation
- **MCP (Model Context Protocol)** server with basic semantic agent discovery
- **A2A (Agent-to-Agent)** protocol basic implementation

### MVP Features (Extensible Foundation)
- **Basic workflow orchestration** with NetworkX graphs (expandable)
- **Agent discovery** via MCP semantic similarity (foundation implemented)
- **Streaming responses** with basic pause/resume (core functionality)
- **Context preservation** across workflows (basic implementation)
- **OPA policy engine** with core security policies (operational)
- **Audit logging** and security validation (basic implementation)
- **Emergency response system** with shutdown capabilities (functional)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Orchestrator  │◄──►│    Planner      │◄──►│     Actor       │
│   (Coordinator) │    │  (Task Decomp)  │    │  (Execution)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Guardian     │    │  Semantic Layer │    │    Observer     │
│   (Policies)    │    │   (MCP Server)  │    │  (Framework)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    Weaviate     │
                       │ (Vector Store)  │
                       └─────────────────┘
```

## 🛠️ Technology Stack

- **Python 3.11+** - Core agent implementation
- **FastAPI** - REST API framework for agent endpoints
- **Docker & Docker Compose** - Containerization and orchestration
- **Weaviate** - Vector database for semantic search
- **Ollama** - Local LLM inference engine
- **LangChain** - LLM integration and workflow management
- **NetworkX** - Graph-based workflow orchestration
- **Redis/TinyDB** - State management and caching
- **MCP Protocol** - Model Context Protocol for standardized communication
- **A2A SDK** - Agent-to-Agent communication framework

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

## 📋 Agent Capabilities (MVP Implementation)

### Orchestrator Agent ✅ MVP
- **Basic workflow coordination** using NetworkX graphs
- **MCP server integration** for agent discovery (foundation)
- **Streaming responses** with A2A protocol basics
- **Context management** across simple workflows
- **Q&A integration** with LangChain (basic implementation)

### Planner Agent ✅ MVP
- **Query decomposition** using LangGraph (basic structured responses)
- **Task breakdown** with simple sequencing
- **Memory persistence** via LangGraph checkpointer
- **Extensible planning framework** ready for advanced features

### Actor Agent ✅ MVP
- **Basic task execution** with LangChain integration
- **Structured response format** with status handling
- **Error handling** and basic recovery
- **Foundation for tool integration** (extensible)

### Guardian Agent ✅ MVP+
- **OPA policy engine integration** with core security policies
- **Emergency response system** with shutdown capabilities
- **Policy validation** with risk assessment
- **Audit logging** and compliance tracking
- **Dashboard and alerting** system integration

### Observer Agent 🚧 Framework Ready
- **Architecture defined** with monitoring interfaces
- **Integration points** established with other agents
- **Extensible framework** for metrics and health monitoring
- **Ready for implementation** of specific monitoring features

## 🔧 Configuration

### Environment Variables
```bash
# LLM Configuration
MODEL_NAME=tinyllama:latest
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

### OPA Policy Engine ✅ MVP
- **Core policies** auto-generated at startup
- **Basic policy evaluation** (core + custom policies)
- **Risk scoring** with basic assessment
- **Fail-safe security defaults** (deny by default)
- **Audit logging** with decision tracking

### Built-in Safety Mechanisms
- **Human veto power** on critical decisions (basic implementation)
- **Emergency shutdown** mechanisms available
- **Self-replication blocking** via core policies
- **Policy modification protection** (agents cannot alter security policies)
- **Basic sensitive data detection**

### Governance Rules (Enforced by OPA)
- ✅ **Self-replication strictly prohibited** by immutable core policies
- ✅ **Policy modification blocked** for all agents except human operators
- ✅ **System-level access denied** to all agents
- ✅ **Network access controlled** to authorized endpoints only
- ✅ **Resource access validated** with basic risk assessment

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

**ABI is a functional MVP (Minimum Viable Product)** demonstrating the core concepts of distributed agent-based infrastructure.  
The system provides a solid foundation with 4/5 agents in basic operational state, OPA policy engine integration, and semantic workflow orchestration. This MVP serves as an extensible platform for building production-ready multi-agent systems.

### Current Implementation Status:
- **Infrastructure**: ✅ Production-ready (Docker, Weaviate, Ollama, MCP Server)
- **Core Agents**: ✅ MVP functional (basic implementations with room for enhancement)
- **Security Layer**: ✅ Operational (OPA integration with emergency systems)
- **Semantic Layer**: ✅ Basic MCP integration (extensible foundation)
- **Observer Agent**: 🚧 Framework ready, implementation pending

### Roadmap to Production:
1. **Enhanced Agent Capabilities** - Expand from basic to advanced functionality
2. **Complete MCP Integration** - Full semantic protocol implementation
3. **Observer Agent Implementation** - Complete the monitoring system
4. **Advanced Security Features** - Enhanced policy engine and audit systems
5. **Production Testing** - Comprehensive integration and performance testing
6. **Tool Ecosystem** - Rich integration with external tools and services

---

## ✨ From Curiosity to Creation: A Personal Note
I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated. At the time, I wanted to study robotics — but when I touched that machine, everything changed. I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big. When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying. Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI. This is for the kids like me, then and now.

## About the Author

**José Luis Martínez** is a systems engineer, AI infrastructure strategist, and creator of the ABI (Agent-Based Infrastructure) paradigm.  
This project is part of an ongoing research effort to democratize intelligent systems and create shared cognition frameworks for open innovation.

Connect on [LinkedIn](https://www.linkedin.com/in/jose-luis-martinez-71195425/) | [Blog](https://designednotmagic.hashnode.dev)