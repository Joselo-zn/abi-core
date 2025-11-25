# What is ABI-Core?

ABI-Core is a framework for building **AI agent systems** that can work together intelligently and securely.

## The Simple Idea

Imagine you have several AI assistants, each specialized in something different:

- 🤖 An agent that **analyzes data**
- 🤖 An agent that **writes reports**
- 🤖 An agent that **answers questions**

**ABI-Core** allows you to:

1. **Create** these agents easily
2. **Connect** them to work together
3. **Discover** them automatically when needed
4. **Protect** them with security policies

## Why Use ABI-Core?

### Without ABI-Core

```python
# You have to do everything manually
llm = ChatOllama(model="qwen2.5:3b")
response = llm.invoke("Analyze this data...")

# How to connect with another agent?
# How to know what agents exist?
# How to apply security?
# Everything is complicated...
```

### With ABI-Core

```bash
# Create a project
abi-core create project my-system

# Add an agent
abi-core add agent analyst --description "Analyzes data"

# Start everything
abi-core run

# Done! Your agent is running
```

## Main Components

### 1. Agents 🤖

**Agents** are AI programs that can:

- Understand natural language
- Execute specific tasks
- Use tools (calculators, APIs, databases)
- Communicate with other agents

**Example**: An agent that answers questions about products.

### 2. Semantic Layer 🧠

The **semantic layer** is like an intelligent directory that:

- Knows what agents exist
- Understands what each agent can do
- Finds the right agent for each task

**Example**: When you ask "Who can analyze sales?", the semantic layer finds the analysis agent.

### 3. Security 🔒

**Guardian** is the security system that:

- Controls who can do what
- Logs all actions
- Applies compliance policies

**Example**: Only the finance agent can execute transactions.

### 4. Orchestration 🎭

The **Orchestrator** coordinates multiple agents:

- Divides complex tasks into subtasks
- Assigns each subtask to the right agent
- Combines the results

**Example**: "Analyze sales and generate report" → Analysis agent + Report agent.

## Visual Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Application                      │
│                  (Web, API, CLI)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                  Orchestrator                           │
│         (Coordinates multiple agents)                   │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ↓           ↓           ↓
    ┌────────┐  ┌────────┐  ┌────────┐
    │Agent 1 │  │Agent 2 │  │Agent 3 │
    │Analyst │  │Writer  │  │Searcher│
    └────────┘  └────────┘  └────────┘
         │           │           │
         └───────────┼───────────┘
                     ↓
         ┌───────────────────────┐
         │   Semantic Layer      │
         │ (Discovers agents)    │
         └───────────────────────┘
                     │
                     ↓
         ┌───────────────────────┐
         │      Guardian         │
         │  (Security & logs)    │
         └───────────────────────┘
```

## Use Cases

### 1. Intelligent Chatbot

A chatbot that can:
- Answer questions
- Search information
- Execute actions

```bash
abi-core create project chatbot
abi-core add agent assistant --description "Help chatbot"
```

### 2. Analysis System

Multiple agents that:
- Collect data
- Analyze trends
- Generate reports

```bash
abi-core create project analysis --with-semantic-layer
abi-core add agent collector --description "Collects data"
abi-core add agent analyzer --description "Analyzes data"
abi-core add agent reporter --description "Generates reports"
```

### 3. Business Assistant

Complete system with:
- Multiple specialized agents
- Automatic discovery
- Security and auditing

```bash
abi-core create project enterprise \
  --with-semantic-layer \
  --with-guardian
```

## Advantages of ABI-Core

### ✅ Easy to Use

```bash
# 3 commands and you have an agent running
abi-core create project my-app
abi-core add agent my-agent
abi-core run
```

### ✅ Scalable

- Start with 1 agent
- Grow to 10, 100 or more
- Agents discover each other automatically

### ✅ Secure

- Access policies
- Complete auditing
- Regulatory compliance

### ✅ Flexible

- Use any AI model (Ollama, OpenAI, etc.)
- Integrate with your existing systems
- Customize everything

## Technologies Included

ABI-Core integrates the best tools:

- **LangChain**: AI framework
- **Ollama**: Local AI models
- **Weaviate**: Vector database
- **OPA**: Policy engine
- **FastAPI**: Web APIs
- **Docker**: Containers

## ABI Philosophy

ABI-Core is based on three principles:

### 1. Semantic Interoperability

Agents must share **meaning**, not just data.

**Bad**: Send `{"data": [1,2,3]}`  
**Good**: Send `{"monthly_sales": [1000, 2000, 3000], "currency": "USD"}`

### 2. Distributed Intelligence

No single model has all the truth. Collaboration is key.

**Bad**: One agent does everything  
**Good**: Multiple specialized agents collaborate

### 3. Governed Autonomy

Agents are autonomous but with clear limits.

**Bad**: Agents without restrictions  
**Good**: Agents with security policies

## Next Steps

Now that you understand what ABI-Core is, learn:

1. [Basic Concepts](03-basic-concepts.md) - Key terms and concepts
2. [Your First Project](04-first-project.md) - Create your first system

## Resources

- [Examples on GitHub](https://github.com/Joselo-zn/abi-core/tree/main/examples)
- [Detailed Architecture](../reference/architecture.md)
- [FAQ](../faq.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
