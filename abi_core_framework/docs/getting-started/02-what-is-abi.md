# What is ABI-Core?

ABI-Core lets you build AI agents that talk to each other, discover each other, and work together — all running inside Docker containers.

## The idea

You write Python functions. ABI turns them into agents that:

- Run as services (Docker containers)
- Find each other automatically (Semantic Layer)
- Talk to each other (A2A protocol)
- Follow security rules (Guardian + OPA)

You focus on the logic. ABI handles the infrastructure.

## What it looks like

```bash
# Create a project with 2 agents
abi-core create project my-system --with-semantic-layer
abi-core add agent researcher --description "Finds information"
abi-core add agent writer --description "Writes reports"
abi-core run
```

That's a running multi-agent system. The researcher can find the writer through the Semantic Layer and send it work via A2A.

## The 4 pieces

### Agents

Python programs that use LLMs to do work. Each agent has:

- **Steps** — deterministic functions that run in order (a DAG)
- **Tasks** — orchestrators that compose steps
- **Tools** — functions the LLM can call

```python
@agent.step(name="analyze")
async def analyze(text):
    result = await invoke(config.LLM_CONFIG, f"Analyze: {text}")
    return {"analysis": result}
```

### Semantic Layer

A search engine for agents. Instead of hardcoding URLs, you search by capability:

```python
agent = await tool_find_agent("someone who can write reports")
# Returns the writer agent's card with its URL and capabilities
```

Uses Weaviate (vector database) under the hood.

### A2A Protocol

How agents talk. Standardized JSON-RPC over HTTP. Any agent can call any other agent the same way:

```python
async for chunk in agent_connection(my_card, target_card, payload):
    # streaming response from the other agent
```

### Guardian

Security gate. Every request can be validated against OPA policies before execution. Blocks unauthorized actions, logs everything.

## How it's different from just using LangChain

| | Raw LangChain | ABI-Core |
|---|---|---|
| Execution | LLM decides order | DAG decides order (deterministic) |
| Multi-agent | You wire it yourself | A2A protocol + semantic discovery |
| Deployment | You figure it out | `docker compose up` |
| Security | Nothing built-in | Guardian + OPA policies |
| Discovery | Hardcoded URLs | Search by capability |

## Next step

👉 [Basic Concepts](03-basic-concepts.md)
