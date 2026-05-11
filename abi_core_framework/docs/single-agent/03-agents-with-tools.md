# Agents with Tools

Tools let your agent do things beyond just talking — call APIs, calculate, search databases.

## What's a tool?

A tool is a function decorated with `@agent.tool`. It works like a step (runs in the DAG) but is also exposed to the LLM so it can decide when to call it.

## Add a tool

Edit `agents/my_agent/tools.py`:

```python
from app import agent


@agent.tool(name="calculate")
async def calculate(expression: str):
    """Calculate a mathematical expression."""
    try:
        result = eval(expression)
        return {"result": str(result)}
    except Exception as e:
        return {"error": str(e)}


@agent.tool(name="get_time")
async def get_time():
    """Get the current date and time."""
    from datetime import datetime
    now = datetime.now()
    return {"time": now.strftime("%Y-%m-%d %H:%M:%S")}
```

## Use a tool from a task

You can call tools directly from tasks, just like steps:

```python
@agent.task(name="process_request", task_id="task-main")
async def process_request(query):
    data = json.loads(query) if isinstance(query, str) else query
    text = data.get("text", "")

    # Call tool directly
    if "time" in text.lower():
        result = await agent.execute_step("get_time")
        yield AgentResponse.result(result)
        return

    # Or let the LLM decide (via the agent's tool-calling capability)
    yield AgentResponse.status("Processing...")
    result = await agent.execute_step("analyze", text=text)
    yield AgentResponse.result(result)
```

## Tool with an external API

```python
@agent.tool(name="search_weather")
async def search_weather(city: str):
    """Get current weather for a city."""
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"}
        )
        data = resp.json()
        current = data["current_condition"][0]
        return {
            "city": city,
            "temp_c": current["temp_C"],
            "description": current["weatherDesc"][0]["value"],
        }
```

## MCP tools (remote)

For tools that live on the Semantic Layer, use `@agent.mcp_tool`:

```python
@agent.mcp_tool(name="find_similar_documents")
```

No function body needed — ABI calls the remote tool via MCP protocol with HMAC authentication. The tool must be registered in your Semantic Layer.

## The difference between step, tool, and mcp_tool

| Decorator | Runs in DAG | LLM can call it | Where it lives |
|-----------|-------------|-----------------|----------------|
| `@agent.step` | ✅ | ❌ | Local function |
| `@agent.tool` | ✅ | ✅ | Local function |
| `@agent.mcp_tool` | ✅ | ✅ | Remote (Semantic Layer) |

## Test it

```bash
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is 42 * 17?"}'
```

## Next step

👉 [Agents with Memory](04-agents-with-memory.md)
