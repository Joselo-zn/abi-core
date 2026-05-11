# Basic Concepts

The terms you'll see everywhere in ABI-Core, explained simply.

## The building blocks

### Step

A function that does one thing. Runs in a fixed order you define — the AI doesn't decide when it runs.

```python
@agent.step(name="classify")
async def classify(text):
    result = await invoke(config.LLM_CONFIG, f"Classify: {text}")
    return {"category": result}
```

### Task

Runs multiple steps in sequence. Can send progress updates to the user while working.

```python
@agent.task(name="process", task_id="task-main")
async def process(query):
    yield AgentResponse.status("Classifying...")
    classification = await agent.execute_step("classify", text=query)
    yield AgentResponse.result(classification)
```

### Tool

A function the AI can decide to call on its own. Useful for things like searching the web or calling APIs.

```python
@agent.tool(name="search_web")
async def search_web(query: str):
    """Search the web for information."""
    return requests.get(f"https://api.search.com?q={query}").json()
```

### Agent

A Python class that wraps everything together. Has an identity, an AI model config, and runs as a service.

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

A JSON file that describes what an agent can do. Other agents use it to find yours and talk to it.

```json
{
  "name": "my-agent",
  "description": "Does useful things",
  "url": "http://my-agent:8000",
  "supportedTasks": ["classify", "summarize"]
}
```

### Semantic Layer

Stores agent cards and lets you search agents by what they do, not by name or address. "Find me someone who can write reports" → returns the writer agent.

### A2A Protocol

The way agents send messages to each other. A standard format so any agent can talk to any other agent.

### Guardian + OPA

Security. Guardian is the gate that checks every request. OPA holds the rules. Together they decide if something is allowed to run.

### AI Model Provider

ABI-Core supports multiple AI model providers through one config dict:

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
You write:          ABI handles:
─────────           ────────────
steps.py      →     Runs them in order
tasks.py      →     Streams progress to the user
tools.py      →     Lets the AI call them
config.py     →     Connects to any AI model
agent_card    →     Makes your agent discoverable
              →     Messaging server (automatic)
              →     Docker container (automatic)
              →     Health checks (automatic)
```

## Quick glossary

| Term | One-line explanation |
|------|---------------------|
| Step | A function that runs in a fixed order. |
| Task | Runs steps and streams progress. |
| Tool | A function the AI can call. |
| Agent Card | Describes what an agent can do (JSON file). |
| Semantic Layer | Finds agents by what they do. |
| A2A | How agents send messages to each other. |
| Guardian | Checks if a request is allowed. |
| OPA | Holds the security rules. |
| invoke() | Calls any AI model with one function. |
| MCPToolkit | Calls tools on the Semantic Layer. |

## Next step

👉 [Your First Project](04-first-project.md)
