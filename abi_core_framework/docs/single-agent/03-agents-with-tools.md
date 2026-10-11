# Agents with Tools

Tools let your agent do things beyond just talking — call APIs, calculate, search databases.

There are two ways to use a tool, and the difference matters:

- **Your code calls it.** You decide when it runs. Predictable, testable, the default.
- **The model calls it.** You hand the model a list of tools and it decides which one, if any. Flexible — and only as reliable as the model.

This page shows both.

## Create the agent

```bash
abi-core add agent --name my_agent --description "Answers with the help of tools" --with-web-interface
```

## Write the tools

Replace the contents of `agents/my_agent/tools.py`:

```python
import ast
import operator
from datetime import datetime

from app import agent

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _evaluate(node):
    """Evaluate +, -, *, /, ** on numbers. Anything else is rejected."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_evaluate(node.operand))
    raise ValueError("only arithmetic is allowed")


@agent.tool(name="calculate")
async def calculate(expression: str):
    """Calculate an arithmetic expression such as '42 * 17'."""
    try:
        return {"result": str(_evaluate(ast.parse(expression, mode="eval").body))}
    except Exception as e:
        return {"error": str(e)}


@agent.tool(name="get_time")
async def get_time():
    """Get the current date and time."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
```

```{warning}
Never pass model output or user input to `eval()`. A tool is code the model can trigger with arguments it chooses — treat those arguments as untrusted. The calculator above parses the expression and only allows arithmetic.
```

## Your code calls the tool

A tool registered with `@agent.tool` can be called by name from a task, exactly like a step:

```python
from app import agent
from abi_core.agent.agent_response import AgentResponse


@agent.task(name="process_request", task_id="task-main")
async def process_request(query, context_id=None):
    if "time" in query.lower():
        result = await agent.execute_step("get_time")
        yield AgentResponse.result(result)
        return

    yield AgentResponse.result({"echo": query})
```

## The model calls the tool

To let the model choose, pass tools to `invoke()`. `invoke()` takes LangChain tools, so wrap the same functions with `StructuredTool`:

```python
from langchain_core.tools import StructuredTool

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke
from tools import calculate, get_time

MODEL_TOOLS = [
    StructuredTool.from_function(coroutine=calculate, name="calculate", description=calculate.__doc__),
    StructuredTool.from_function(coroutine=get_time, name="get_time", description=get_time.__doc__),
]


@agent.step(name="answer_with_tools")
async def answer_with_tools(text):
    """Let the model decide whether it needs the calculator or the clock."""
    answer = await invoke(config.LLM_CONFIG, text, tools=MODEL_TOOLS)
    return {"answer": answer}
```

Then call that step from your task: `await agent.execute_step("answer_with_tools", text=query)`.

`coroutine=` matters: the tools are `async`, and passing them as `func=` would make LangChain run them without awaiting them.

```{note}
If an agent has **no** `@agent.task` at all, every request goes to the agent's built-in model loop, and every `@agent.tool` without `depends_on` is offered to the model automatically — no `invoke()` needed. Once you add a task, the task is in charge, and the model only sees the tools you pass to `invoke()`.
```

## Tool with an external API

```python
import httpx

from app import agent


@agent.tool(name="search_weather")
async def search_weather(city: str):
    """Get current weather for a city."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://wttr.in/{city}", params={"format": "j1"})
        current = resp.json()["current_condition"][0]
        return {
            "city": city,
            "temp_c": current["temp_C"],
            "description": current["weatherDesc"][0]["value"],
        }
```

## MCP tools (remote)

For tools that live on the Semantic Layer, register them by name. There's no local function — the call goes over MCP, signed with your agent card:

```python
from app import agent

agent.mcp_tool(name="search_tool_registry", input_map={"query": "$input.query"})
```

To prepare the call's arguments first, decorate a function. It receives the node's inputs and returns the dict of arguments; the node's output is the tool's result:

```python
@agent.mcp_tool(name="search_tool_registry", input_map={"query": "$input.query"})
async def search_tool_registry(query):
    return {"query": query.strip()}
```

This adds a node to the agent's step graph (the DAG). The tool must exist on your Semantic Layer — see [Extending the Semantic Layer](../semantic-layer/04-extending-semantic-layer.md). To call a Semantic Layer tool from inside a step or task instead, use [MCPToolkit](../semantic-layer/05-mcp-toolkit.md).

## Step, tool, and mcp_tool

| Decorator | Your code can call it | The model can call it | Where it runs |
|-----------|-----------------------|-----------------------|---------------|
| `@agent.step` | ✅ | ❌ | Local function |
| `@agent.tool` | ✅ | ✅ (via `invoke(tools=...)`, or automatically when the agent has no tasks) | Local function |
| `agent.mcp_tool` | ✅ (as a DAG node) | ❌ | Remote (Semantic Layer) |

An `@agent.tool` with `depends_on=[...]` is a DAG node fed by another step's output, so it is never offered to the model.

## Test it

```bash
curl -N -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What time is it?"}'
```

## Next step

👉 [Agents with Memory](04-agents-with-memory.md)
