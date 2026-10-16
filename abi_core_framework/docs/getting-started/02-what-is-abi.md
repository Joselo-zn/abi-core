# What is ABI-Core?

Most AI projects start as one clever prompt and end as a pile of scripts nobody dares to touch. Agents that reach each other through hard-coded addresses. Security bolted on the week before launch. A demo that only runs on one laptop.

I'm ABI. You write plain Python functions; I turn them into agents that run in their own containers, find each other by what they can do, talk through one protocol, and check the rules before they act. This page is the map: four pieces, and how they fit.

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
abi-core create project --name my-system --with-semantic-layer
abi-core add agent --name researcher --description "Finds information"
abi-core add agent --name writer --description "Writes reports"
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

## How it's different from wiring agents yourself

| | A typical hand-wired agent stack | ABI-Core |
|---|---|---|
| Execution | The model decides what runs next | Your code decides; the model works inside steps |
| Multi-agent | You connect every pair yourself | Agents find each other by capability |
| Coordination | Agents talk until they agree | Agents hand over real work, checked by code |
| Deployment | You figure it out | Every agent is a container; `abi-core run` |
| Security | Added later, if at all | A rules engine checks requests before they run |
| Models | Usually one cloud provider | Local by default (Ollama), any provider per agent |

Want the long version? Read [Why ABI-Core](../why-abi-core.md).

## Next step

👉 [Basic Concepts](03-basic-concepts.md)
