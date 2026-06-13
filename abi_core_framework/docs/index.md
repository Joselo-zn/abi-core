# ABI-Core Documentation

⭐ **Into AI agents?** [Star ABI-Core on GitHub](https://github.com/Joselo-zn/abi-core) — it helps others discover the project.

Welcome to **ABI-Core** documentation — build AI agents that work together, find each other, and follow the rules. All from Python.

```{toctree}
:maxdepth: 2
:hidden:
:caption: 1. Fundamentals

getting-started/01-installation
getting-started/02-what-is-abi
getting-started/03-basic-concepts
getting-started/04-first-project
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 2. Single Agents

single-agent/01-first-agent
single-agent/02-simple-chatbot
single-agent/03-agents-with-tools
single-agent/04-agents-with-memory
single-agent/05-testing-agents
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 3. Multi-Agent Basics

multi-agent-basics/01-why-multiple-agents
multi-agent-basics/02-agent-cards
multi-agent-basics/03-agent-communication
multi-agent-basics/04-first-multi-agent-system
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 4. Semantic Layer

semantic-layer/01-what-is-semantic-layer
semantic-layer/02-agent-discovery
semantic-layer/03-semantic-search
semantic-layer/04-extending-semantic-layer
semantic-layer/05-mcp-toolkit
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 5. Advanced Orchestration

orchestration/01-planner-orchestrator
orchestration/02-multi-agent-workflows
orchestration/03-dependency-management
orchestration/04-result-synthesis
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 6. RAG & Knowledge

rag/01-what-is-rag
rag/02-vector-databases
rag/03-embeddings-search
rag/04-agents-with-rag
```

```{toctree}
:maxdepth: 2
:hidden:
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
:hidden:
:caption: 8. Production

production/01-model-serving
production/02-monitoring-logs
production/03-troubleshooting
production/04-deployment
production/05-artifact-store
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: 9. Reference

reference/cli-reference
reference/api-reference
reference/environment-variables
reference/architecture
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: Additional Resources

migration/a2a-sdk-1.0
changelog
faq
roadmap
```

## Hello, I'm ABI

I help you build AI agents that actually work together. You write the logic, I handle everything else — running them, connecting them, keeping them secure. One `pip install`, a few decorators, and your agents are live.

ABI-Core is a Python framework for creating AI agent systems. You write agents as simple Python functions. ABI packages them, runs them, connects them to each other, and makes sure they play by the rules. No glue code, no infrastructure headaches.

## What makes ABI different

- **You control the order** — Your code decides what runs when. The AI thinks, but your graph executes. No surprises, no random tool calls.
- **Any AI model** — Ollama running on your laptop, OpenAI, Gemini, Grok, Anthropic — switch by changing one line. Your agent code stays the same.
- **Agents find each other** — You don't hardcode who talks to who. Agents describe what they can do, and others find them by asking "who can do X?"
- **They talk to each other** — A standard protocol so any agent can call any other agent. Like HTTP for AI agents.
- **Security built in** — Every action can be checked against rules before it runs. Not an afterthought — it's part of the system.
- **Agents that appear and disappear** — Need a specialist for one task? The system creates one, it does the job, delivers the result, and cleans up after itself. *(alpha)*
- **One command to start** — `abi-core create swarm` gives you a complete multi-agent system ready to run. No manual wiring. *(alpha)*

## Quick Start

```bash
pip install abi-core-ai

abi-core create project my-system --with-semantic-layer
cd my-system
abi-core add agent my-agent --description "My first agent" --with-web-interface
abi-core run
```

That's it. You now have an AI agent running in a Docker container with an HTTP endpoint you can talk to.

## Learning Paths

### Build your first agent

Go from zero to a running agent that talks to an AI model and responds in real-time:

1. [Installation](getting-started/01-installation.md)
2. [What is ABI-Core?](getting-started/02-what-is-abi.md)
3. [Basic Concepts — Steps, Tasks, Tools](getting-started/03-basic-concepts.md)
4. [Your First Project](getting-started/04-first-project.md)
5. [Your First Agent](single-agent/01-first-agent.md)
6. [Adding Tools](single-agent/03-agents-with-tools.md)

### Connect multiple agents

Make agents find each other and work together on tasks:

1. [Why Multiple Agents?](multi-agent-basics/01-why-multiple-agents.md)
2. [Agent Cards — Identity & Discovery](multi-agent-basics/02-agent-cards.md)
3. [How Agents Talk to Each Other](multi-agent-basics/03-agent-communication.md)
4. [The Semantic Layer — Search by Capability](semantic-layer/01-what-is-semantic-layer.md)
5. [MCPToolkit — Call Remote Tools](semantic-layer/05-mcp-toolkit.md)
6. [Your First Multi-Agent System](multi-agent-basics/04-first-multi-agent-system.md)

### Orchestrate complex workflows

Break big tasks into pieces, assign them to agents, combine the results:

1. [Planner & Orchestrator](orchestration/01-planner-orchestrator.md)
2. [Multi-Agent Workflows](orchestration/02-multi-agent-workflows.md)
3. [Dependency Management](orchestration/03-dependency-management.md)
4. [Result Synthesis](orchestration/04-result-synthesis.md)

### Secure and deploy

Add security rules, monitor your system, and deploy to production:

1. [Guardian Service](security/01-guardian-service.md)
2. [Writing Security Rules (OPA)](security/02-opa-policies.md)
3. [Agent-to-Agent Validation](security/06-a2a-validation.md)
4. [Model Serving Strategies](production/01-model-serving.md)
5. [Monitoring & Logs](production/02-monitoring-logs.md)
6. [Deployment](production/04-deployment.md)

## Examples

Progressive examples from a simple chatbot to a full multi-agent swarm, including a step-by-step tutorial:

👉 [abi-core-examples](https://github.com/Joselo-zn/abi-core-examples)

## Community & Support

- **GitHub**: [github.com/Joselo-zn/abi-core](https://github.com/Joselo-zn/abi-core)
- **PyPI**: [pypi.org/project/abi-core-ai](https://pypi.org/project/abi-core-ai/)
- **Issues**: [Report bugs or request features](https://github.com/Joselo-zn/abi-core/issues)

## License

ABI-Core is released under the Apache 2.0 License.

---

**Built with ❤️ by [José Luis Martínez](https://github.com/Joselo-zn)**
Creator of **ABI (Agent-Based Infrastructure)** — redefining how intelligent systems interconnect.

✨ **From Curiosity to Creation: A Personal Note**

I first saw a computer in 1995. My dad had received a Windows 3.11 machine as payment for a job. I was fascinated.
At the time, I wanted to study robotics — but when I touched that machine, everything changed.

I didn't understand what the Internet was, and I had no idea where to go… but even in that confusion, I felt something big.
When I wrote my first Visual C++ program in 1999, I felt like a hacker. When I built my first web page, full of GIFs, I was flying.

Nobody taught me. I just read manuals. And now, years later, that journey continues — not just as a coder, but as the creator of ABI.
This is for the kids like me, then and now.
