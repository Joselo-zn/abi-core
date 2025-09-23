# ABI – Agent-Based Infrastructure
Created and maintained by José Luis Martínez

**ABI** is a paradigm shift in how we design, deploy, and interact with intelligent systems.

Instead of centralizing superintelligence behind APIs or monolithic LLMs, ABI implements a distributed, agent-based architecture where cognition is shared, decisions are explainable, and humans remain in control.

This repository contains a **fully functional implementation** of ABI: a human-supervised, auditable infrastructure that enables universities, NGOs, independent labs, and open-source communities to access and build on top of intelligent, modular agents.

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

## 🚀 What's Implemented

### Multi-Agent System
- **5 specialized agents** working in coordination:
  - **Orchestrator**: Coordinates workflows and manages agent communication
  - **Planner**: Decomposes queries into executable task sequences
  - **Actor**: Executes tasks and integrates with external tools
  - **Guardian**: Enforces policies and audits agent behavior
  - **Observer**: Monitors system state and provides insights

### Core Infrastructure
- **Docker-based deployment** with full containerization
- **Weaviate vector database** for semantic search and embeddings
- **Ollama integration** for local LLM execution
- **FastAPI** REST APIs for each agent
- **MCP (Model Context Protocol)** for standardized communication
- **A2A (Agent-to-Agent)** protocol for inter-agent messaging

### Advanced Features
- **Workflow orchestration** with dependency management
- **Semantic agent discovery** based on task requirements
- **Real-time streaming** responses and status updates
- **Context preservation** across multi-step workflows
- **Policy enforcement** and safety mechanisms
- **Audit trails** for all agent interactions

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
│   (Policies)    │    │   (MCP Server)  │    │  (Monitoring)   │
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
- **Orchestrator API**: http://localhost:8082
- **Actor Agent API**: http://localhost:8083
- **Semantic Layer**: http://localhost:10100
- **Weaviate Console**: http://localhost:8080

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

### Orchestrator Agent
- Workflow coordination and task distribution
- Context management across agent interactions
- Real-time streaming of results
- Human-in-the-loop decision points

### Planner Agent
- Query decomposition into executable tasks
- Agent selection based on semantic matching
- Dependency resolution and sequencing
- Resource allocation planning

### Actor Agent
- Task execution with tool integration
- External API and system interactions
- Structured result reporting
- Error handling and recovery

### Guardian Agent
- Policy enforcement and compliance checking
- Security audit and access control
- Behavioral monitoring and alerts
- Emergency shutdown capabilities

### Observer Agent
- System state monitoring and metrics
- Performance analysis and optimization
- Anomaly detection and reporting
- Health checks and diagnostics

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

### Built-in Safety Mechanisms
- **Human veto power** on all critical decisions
- **Immutable audit logs** for all agent communications
- **Network isolation** between agent subnets
- **Resource limits** and access controls
- **Policy validation** before task execution

### Governance Rules
- Agents cannot modify firewall or network rules
- Self-replication is strictly prohibited
- All inter-agent communication is logged
- Emergency shutdown mechanisms are always available
- Human oversight is required for sensitive operations

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [Agent Protocols](docs/agent_protocols.md)
- [Governance Framework](docs/gobernance.md)
- [Core Stack Details](CORE-STACK.md)
- [Infrastructure Guide](INFRA-STACK.md)
- [Development Roadmap](ROADMAP.md)

## 🤝 Contributing

ABI is an open-source project welcoming contributions from the community. Whether you're interested in:

- Adding new agent types
- Improving the semantic layer
- Enhancing security mechanisms
- Expanding tool integrations
- Writing documentation

Please see our contribution guidelines and join the discussion.

## 📄 License & Philosophy

Distributed under the [Apache License 2.0](LICENSE).

Read our [Manifesto](MANIFIESTO.md) and [Whitepaper](WHITEPAPER.md) to understand the philosophical foundations of ABI.

## Status

**ABI is a functional prototype** ready for deployment and experimentation.  
The core infrastructure is implemented and operational, with active development continuing on advanced features and optimizations.

---

## ✨ From Curiosity to Creation: A Personal Note
I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated. At the time, I wanted to study robotics — but when I touched that machine, everything changed. I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big. When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying. Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI. This is for the kids like me, then and now.

## About the Author

**José Luis Martínez** is a systems engineer, AI infrastructure strategist, and creator of the ABI (Agent-Based Infrastructure) paradigm.  
This project is part of an ongoing research effort to democratize intelligent systems and create shared cognition frameworks for open innovation.

Connect on [LinkedIn](https://www.linkedin.com/in/jose-luis-martinez-71195425/) | [Blog](https://designednotmagic.hashnode.dev)