# ABI-Core Documentation

Welcome to **ABI-Core** documentation — a comprehensive framework for building AI agent systems with semantic layers, orchestration, and security policies.

```{toctree}
:maxdepth: 2
:caption: 1. Fundamentals

getting-started/01-installation
getting-started/02-what-is-abi
getting-started/03-basic-concepts
getting-started/04-first-project
```

```{toctree}
:maxdepth: 2
:caption: 2. Single Agents

single-agent/01-first-agent
single-agent/02-simple-chatbot
single-agent/03-agents-with-tools
single-agent/04-agents-with-memory
single-agent/05-testing-agents
```

```{toctree}
:maxdepth: 2
:caption: 3. Multi-Agent Basics

multi-agent-basics/01-why-multiple-agents
multi-agent-basics/02-agent-cards
multi-agent-basics/03-agent-communication
multi-agent-basics/04-first-multi-agent-system
```

```{toctree}
:maxdepth: 2
:caption: 4. Semantic Layer

semantic-layer/01-what-is-semantic-layer
semantic-layer/02-agent-discovery
semantic-layer/03-semantic-search
semantic-layer/04-extending-semantic-layer
semantic-layer/05-mcp-toolkit
```

```{toctree}
:maxdepth: 2
:caption: 5. Advanced Orchestration

orchestration/01-planner-orchestrator
orchestration/02-multi-agent-workflows
orchestration/03-dependency-management
orchestration/04-result-synthesis
```

```{toctree}
:maxdepth: 2
:caption: 6. RAG & Knowledge

rag/01-what-is-rag
rag/02-vector-databases
rag/03-embeddings-search
rag/04-agents-with-rag
```

```{toctree}
:maxdepth: 2
:caption: 7. Security & Policies

security/01-guardian-service
security/02-opa-policies
security/03-policy-development
security/04-user-validation
security/05-audit-compliance
security/06-a2a-validation
```

```{toctree}
:maxdepth: 2
:caption: 8. Production

production/01-model-serving
production/02-monitoring-logs
production/03-troubleshooting
production/04-deployment
```

```{toctree}
:maxdepth: 2
:caption: 9. Reference

reference/cli-reference
reference/api-reference
reference/environment-variables
reference/architecture
```

```{toctree}
:maxdepth: 1
:caption: Additional Resources

changelog
faq
roadmap
```

## What is ABI-Core?

**ABI-Core** (Agent-Based Infrastructure Core) is a production-ready framework that combines:

> 🎉 **v1.2.0 Released!** — Now featuring modular architecture, enhanced Open WebUI compatibility, and improved web interfaces for seamless agent development.

- 🤖 **AI Agents** — LangChain-powered agents with A2A (Agent-to-Agent) communication
- 🧠 **Semantic Layer** — Vector embeddings and distributed knowledge management
- 🔒 **Security** — OPA-based policy enforcement and access control
- 🌐 **Web Interfaces** — FastAPI-based REST APIs and real-time dashboards
- 📦 **Containerization** — Docker-ready deployments with orchestration

## Quick Start

```bash
# Install ABI-Core
pip install abi-core-ai

# Create your first project
abi-core create project my-ai-system --with-semantic-layer

# Navigate to project
cd my-ai-system

# Provision models
abi-core provision-models

# Create an agent
abi-core add agent my-agent --description "My first AI agent"

# Start the system
abi-core run
```

## Learning Paths

### 🎯 For Beginners
1. [Installation](getting-started/01-installation.md)
2. [What is ABI-Core?](getting-started/02-what-is-abi.md)
3. [Your First Project](getting-started/04-first-project.md)
4. [Your First Agent](single-agent/01-first-agent.md)

### 🚀 For Developers
1. [Agents with Tools](single-agent/03-agents-with-tools.md)
2. [Agent Communication](multi-agent-basics/03-agent-communication.md)
3. [Semantic Layer](semantic-layer/01-what-is-semantic-layer.md)
4. [Multi-Agent Workflows](orchestration/02-multi-agent-workflows.md)

### 🏢 For Production
1. [Model Serving](production/01-model-serving.md)
2. [Security with Guardian](security/01-guardian-service.md)
3. [Monitoring & Logs](production/02-monitoring-logs.md)
4. [Deployment](production/04-deployment.md)

## Community & Support

- **GitHub**: [github.com/Joselo-zn/abi-core](https://github.com/Joselo-zn/abi-core)
- **Issues**: [Report bugs or request features](https://github.com/Joselo-zn/abi-core/issues)
- **Discussions**: [Join the conversation](https://github.com/Joselo-zn/abi-core/discussions)
- **Email**: jl.mrtz@gmail.com

## License

ABI-Core is released under the Apache 2.0 License. See [LICENSE](https://github.com/Joselo-zn/abi-core/blob/main/LICENSE) for details.

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
