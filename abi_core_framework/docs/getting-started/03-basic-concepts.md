# Basic Concepts

The terms you'll see everywhere in ABI-Core, explained simply.

## The building blocks

### Step

A function that does one thing. Runs in a fixed order (DAG), not decided by the LLM.

```python
@agent.step(name="classify")
async def classify(text):
    result = await invoke(config.LLM_CONFIG, f"Classify: {text}")
    return {"category": result}
```

### Task

Orchestrates multiple steps. Can do branching, parallel execution, and streaming.

```python
@agent.task(name="process", task_id="task-main")
async def process(query):
    yield AgentResponse.status("Classifying...")
    classification = await agent.execute_step("classify", text=query)
    yield AgentResponse.result(classification)
```

### Tool

A step that the LLM can also call on its own. Useful for external APIs.

```python
@agent.tool(name="search_web")
async def search_web(query: str):
    """Search the web for information."""
    return requests.get(f"https://api.search.com?q={query}").json()
```

### Agent

A Python class that wraps everything together. Has an identity, an LLM config, and runs as a service.

```python
class MyAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-agent",
            description="Does useful things",
            llm_config={"provider": "ollama", "model": "qwen2.5:3b"},
            system_prompt="You are a helpful assistant.",
        )
```

## The infrastructure

### Agent Card

A JSON file that describes what an agent can do. Other agents use it to find and talk to you.

```json
{
  "name": "my-agent",
  "description": "Does useful things",
  "url": "http://my-agent:8000",
  "supportedTasks": ["classify", "summarize"]
}
```

### Semantic Layer

Stores agent cards in a vector database (Weaviate). Lets you search agents by what they do, not by name.

### A2A Protocol

The way agents send messages to each other. JSON-RPC over HTTP with streaming support.

### Guardian + OPA

Security. Guardian is the gate, OPA evaluates the rules. Together they decide if a request is allowed.

### LLM Provider

ABI-Core supports multiple LLM backends through one config dict:

| Provider | Config |
|----------|--------|
| Ollama (local) | `{"provider": "ollama", "model": "qwen2.5:3b"}` |
| OpenAI | `{"provider": "openai", "model": "gpt-4o", "api_key": "..."}` |
| Gemini | `{"provider": "gemini", "model": "gemini-pro", "api_key": "..."}` |
| Grok | `{"provider": "grok", "model": "grok-1", "api_key": "..."}` |
| Anthropic | `{"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "..."}` |
| Bedrock | `{"provider": "bedrock", "model": "anthropic.claude-3-sonnet"}` |

Switch providers by changing the dict. No code changes.

## How they fit together

```
You write:          ABI provides:
─────────           ─────────────
steps.py      →     DAG execution engine
tasks.py      →     Streaming + routing
tools.py      →     LLM tool integration
config.py     →     Multi-provider LLM
agent_card    →     Semantic discovery
              →     A2A server (automatic)
              →     Docker container (automatic)
              →     Health checks (automatic)
```

## Quick glossary

| Term | One-line explanation |
|------|---------------------|
| Step | A function in the DAG. Deterministic. |
| Task | Orchestrates steps. Streams responses. |
| Tool | A step the LLM can call. |
| Agent Card | JSON describing an agent's capabilities. |
| Semantic Layer | Finds agents by what they do (Weaviate). |
| A2A | Agent-to-agent communication protocol. |
| Guardian | Security gate. Blocks unauthorized requests. |
| OPA | Policy engine. Rules written in Rego. |
| invoke() | Calls any LLM with one function. |
| MCPToolkit | Calls remote tools on the Semantic Layer. |

## Next step

👉 [Your First Project](04-first-project.md)
