# What is ABI-Core?

ABI-Core lets you build AI agents that talk to each other, discover each other, and work together — all running inside Docker containers.

## The idea

You write Python functions. ABI turns them into agents that:

- Run as independent services (each in its own Docker container)
- Find each other automatically (no hardcoded addresses)
- Talk to each other (a standard messaging protocol)
- Follow security rules (checked before every action)

You focus on the logic. ABI handles the rest.

## What it looks like

```bash
# Create a project with 2 agents
abi-core create project my-system --with-semantic-layer
abi-core add agent researcher --description "Finds information"
abi-core add agent writer --description "Writes reports"
abi-core run
```

That's a running multi-agent system. The researcher can find the writer and send it work — without you wiring them together manually.

## The 4 pieces

### Agents

Python programs that use AI models to do work. Each agent has:

- **Steps** — functions that run in a fixed order you define
- **Tasks** — orchestrators that compose steps into workflows
- **Tools** — functions the AI can decide to call when needed

```python
@agent.step(name="analyze")
async def analyze(text):
    result = await invoke(config.LLM_CONFIG, f"Analyze: {text}")
    return {"analysis": result}
```

### Semantic Layer

A search engine for agents. Instead of hardcoding addresses, you search by what you need:

```python
agent = await tool_find_agent("someone who can write reports")
# Returns the writer agent with its address and capabilities
```

Under the hood it uses a vector database (Weaviate) to match by meaning, not exact words.

### A2A Protocol

How agents talk to each other. A standard message format so any agent can call any other agent the same way:

```python
async for chunk in agent_connection(my_card, target_card, payload):
    # streaming response from the other agent
```

### Guardian

The security gate. Every request can be checked against rules before it runs. Blocks unauthorized actions, logs everything.

## How it's different from just using LangChain

| | Raw LangChain | ABI-Core |
|---|---|---|
| Execution | AI decides order | Your code decides order |
| Multi-agent | You wire it yourself | Agents find each other automatically |
| Deployment | You figure it out | `docker compose up` |
| Security | Nothing built-in | Built-in rules engine |
| Discovery | Hardcoded addresses | Search by capability |

## Next step

👉 [Basic Concepts](03-basic-concepts.md)
