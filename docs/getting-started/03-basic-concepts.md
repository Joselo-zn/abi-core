# Basic Concepts

Before you start building, it's important to understand some key concepts in ABI-Core.

## Agent

An **agent** is an AI program that can:

- Understand and generate natural language
- Execute specific tasks
- Use tools and functions
- Communicate with other agents

**Analogy**: Think of an agent as a specialized employee in your company.

**Example**:
```python
# A simple agent
class AssistantAgent:
    def respond(self, question):
        # Uses AI to respond
        return "Here's your answer..."
```

## Project

A **project** is a container for your agent system. It includes:

- One or more agents
- Services (semantic layer, security)
- Configuration
- Docker files

**Analogy**: A project is like a company with several departments (agents).

**Structure**:
```
my-project/
├── agents/          # Your agents
├── services/        # Support services
├── compose.yaml     # Docker configuration
└── .abi/           # Project metadata
```

## Agent Card

An **agent card** is a document that describes:

- What the agent can do
- How to communicate with it
- What tasks it supports

**Analogy**: It's like a professional business card.

**Example**:
```json
{
  "name": "Analyst Agent",
  "description": "Analyzes sales data",
  "url": "http://localhost:8000",
  "tasks": ["analyze_sales", "generate_report"]
}
```

## Semantic Layer

The **semantic layer** is a service that:

- Registers all available agents
- Finds the right agent for each task
- Uses intelligent search (embeddings)

**Analogy**: It's like an intelligent phone directory.

**Usage**:
```python
# Search for an agent
agent = find_agent("analyze sales data")
# Returns: Analyst Agent
```

## A2A Protocol

**A2A** is the protocol that allows agents to communicate with each other.

**Analogy**: It's like email between company employees.

**Example**:
```python
# Agent A sends message to Agent B
await agent_a.send_message(
    destination="agent_b",
    message="Analyze this data"
)
```

## LLM (Large Language Model)

An **LLM** is the "brain" of the agent. It's the AI model that:

- Understands natural language
- Generates responses
- Reasons about problems

**Common models**:
- `qwen2.5:3b` (default in ABI-Core)
- `llama3.2:3b`
- `mistral:7b`

## Ollama

**Ollama** is the server that runs LLMs locally.

**Analogy**: It's like having your own AI server instead of using cloud services.

**Advantages**:
- ✅ Privacy (everything local)
- ✅ No API costs
- ✅ No usage limits

## Model Serving

There are two ways to serve models:

### Centralized (Recommended)

One Ollama serves all agents:

```
┌─────────────┐
│   Ollama    │ ← All agents use this
└─────────────┘
      ↑
      ├─── Agent 1
      ├─── Agent 2
      └─── Agent 3
```

**Advantages**: Less resources, easier to manage

### Distributed

Each agent has its own Ollama:

```
Agent 1 ← Ollama 1
Agent 2 ← Ollama 2
Agent 3 ← Ollama 3
```

**Advantages**: Complete isolation, independent versions

## Guardian

**Guardian** is the security service that:

- Controls permissions
- Logs all actions
- Applies policies

**Analogy**: It's like the security department of a company.

## OPA (Open Policy Agent)

**OPA** is the engine that evaluates security policies.

**Policy example**:
```rego
# Only the finance agent can execute transactions
allow if {
    input.agent == "finance"
    input.action == "execute_transaction"
}
```

## Embeddings

**Embeddings** are numerical representations of text that allow:

- Search by meaning (not just exact words)
- Find similar content
- Group related information

**Example**:
```
"analyze sales" → [0.2, 0.8, 0.1, ...]
"examine revenue" → [0.3, 0.7, 0.2, ...]
# These are similar!
```

## Weaviate

**Weaviate** is the vector database that:

- Stores embeddings
- Performs semantic searches
- Finds agents by capability

## Docker and Docker Compose

**Docker** packages applications in containers.  
**Docker Compose** orchestrates multiple containers.

**Analogy**: Docker is like a standard shipping container, Docker Compose is the logistics system.

**In ABI-Core**:
```yaml
# compose.yaml
services:
  my-agent:
    build: ./agents/my-agent
    ports:
      - "8000:8000"
```

## Streaming

**Streaming** is sending responses in real-time, word by word.

**Without streaming**:
```
User: "Explain AI"
[wait 10 seconds]
Agent: "Artificial intelligence is..."
```

**With streaming**:
```
User: "Explain AI"
Agent: "Artificial" "intelligence" "is"...
```

## Context ID and Task ID

- **Context ID**: Identifies a complete conversation
- **Task ID**: Identifies a specific task

**Example**:
```
Context ID: "conversation-001"
  ├─ Task ID: "question-1"
  ├─ Task ID: "question-2"
  └─ Task ID: "question-3"
```

## Workflow

A **workflow** is a sequence of tasks executed by multiple agents.

**Example**:
```
1. Collector Agent → Gets data
2. Analyst Agent → Analyzes data
3. Reporter Agent → Generates report
```

## Planner and Orchestrator

- **Planner**: Divides complex tasks into subtasks
- **Orchestrator**: Executes subtasks and coordinates agents

**Example**:
```
User: "Analyze sales and generate report"

Planner:
  ├─ Task 1: Analyze sales → Analyst Agent
  └─ Task 2: Generate report → Reporter Agent

Orchestrator:
  ├─ Executes Task 1
  ├─ Executes Task 2
  └─ Combines results
```

## MCP (Model Context Protocol)

**MCP** is the protocol for communication between agents and the semantic layer.

**Main functions**:
- `find_agent()`: Search for an agent
- `list_agents()`: List all agents
- `check_health()`: Verify agent status

## Quick Glossary

| Term | Meaning |
|------|---------|
| **Agent** | AI program that executes tasks |
| **Agent Card** | Description of agent capabilities |
| **A2A** | Agent-to-agent communication protocol |
| **LLM** | Language model (agent's brain) |
| **Ollama** | Server to run LLMs locally |
| **Semantic Layer** | Agent discovery service |
| **Guardian** | Security and policy service |
| **OPA** | Policy evaluation engine |
| **Embeddings** | Numerical representation of text |
| **Weaviate** | Vector database |
| **Streaming** | Real-time responses |
| **Workflow** | Multi-agent task sequence |
| **Planner** | Divides complex tasks |
| **Orchestrator** | Coordinates task execution |
| **MCP** | Communication protocol with semantic layer |

## Next Steps

Now that you know the basic concepts:

1. [Create your first project](04-first-project.md)
2. [Create your first agent](../single-agent/01-first-agent.md)

## Resources

- [Complete Architecture](../reference/architecture.md)
- [CLI Reference](../reference/cli-reference.md)
- [FAQ](../faq.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
