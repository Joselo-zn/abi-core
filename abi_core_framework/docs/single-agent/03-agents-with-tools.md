# Agents with Tools

Agents can use tools to perform specific actions like calculating, searching information, or calling APIs.

## What are Tools?

**Tools** are functions that the agent can call to:
- Perform calculations
- Search information
- Call external APIs
- Access databases

## Decorator-Based Tools (Recommended)

The simplest way to add tools is using `@agent.tool()` and `@agent.mcp_tool()` decorators on the `AbiCore` instance:

```python
from my_agent import MyAgent
from abi_core.agent import AbiCore

agent = AbiCore()

# Local tool — available to the LLM + runs in the DAG
@agent.tool(name="calculate")
def calculate(expression: str) -> str:
    """Calculate a mathematical expression"""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"

# MCP remote tool — calls your semantic layer via MCPToolkit
@agent.mcp_tool(
    name="bigquery_search",
    input_map={"query": "$input.user_query"},
)

agent.run(MyAgent())
```

### Deterministic Task Pipelines

Use `@agent.task()` for strict execution order (the LLM never decides when to run these):

```python
agent = AbiCore()

@agent.task(name="fetch_data")
def fetch_data(query):
    return {"rows": db.execute(query)}

@agent.task(
    name="clean_data",
    depends_on=["fetch_data"],
    input_map={"raw": "$fetch_data.rows"},
)
def clean_data(raw):
    return {"cleaned": [r for r in raw if r["valid"]]}

@agent.task(
    name="store_results",
    depends_on=["clean_data"],
    input_map={"data": "$clean_data.cleaned"},
)
def store_results(data):
    db.insert(data)
    return {"stored": len(data)}

agent.run(MyAgent())
```

The tasks run in topological order via `ToolExecutionGraph` — a LangGraph-based DAG that prevents the LLM from executing steps out of order.

## LangChain Tools (Classic Approach)

### Step 1: Define Tools

```python
from langchain.tools import tool

@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression"""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
    # In production, you'd call a real API
    return f"Weather in {city} is sunny, 72°F"

@tool
def search_web(query: str) -> str:
    """Search information on the web"""
    # In production, you'd use a search API
    return f"Results for '{query}': [simulated information]"
```

### Step 2: Create the Agent

```python
from abi_core.agent.agent import AbiAgent
from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
import os

class ToolAgent(AbiAgent):
    def __init__(self):
        super().__init__(
            agent_name='tool-agent',
            description='Agent with tools'
        )
        self.setup_agent_with_tools()
    
    def setup_agent_with_tools(self):
        # LLM
        llm = ChatOllama(
            model=os.getenv('MODEL_NAME', 'qwen2.5:3b'),
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
            temperature=0.1
        )
        
        # Tools
        tools = [calculate, get_weather, search_web]
        
        # Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant with access to tools. "
                       "Use tools when necessary."),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        # Create agent
        agent = create_tool_calling_agent(llm, tools, prompt)
        
        # Executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True
        )
    
    def process(self, enriched_input):
        query = enriched_input['query']
        
        # Execute with tools
        result = self.agent_executor.invoke({"input": query})
        
        return {
            'result': result['output'],
            'query': query
        }
```

## Usage Examples

```bash
# Calculate
curl -X POST http://localhost:8000/stream \
  -d '{"query": "What is 25 * 4?", "context_id": "test", "task_id": "1"}'
# Response: "Result: 100"

# Weather
curl -X POST http://localhost:8000/stream \
  -d '{"query": "What's the weather in Madrid?", "context_id": "test", "task_id": "2"}'
# Response: "Weather in Madrid is sunny, 72°F"

# Search
curl -X POST http://localhost:8000/stream \
  -d '{"query": "Search for Python information", "context_id": "test", "task_id": "3"}'
```

## Advanced Tools

### Tool with Real API

```python
@tool
def get_crypto_price(symbol: str) -> str:
    """Get current price of a cryptocurrency"""
    import requests
    
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': symbol.lower(),
            'vs_currencies': 'usd'
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        price = data[symbol.lower()]['usd']
        return f"The price of {symbol} is ${price} USD"
    except Exception as e:
        return f"Error getting price: {str(e)}"
```

### Tool with Database

```python
@tool
def query_user(user_id: str) -> str:
    """Query user information"""
    import sqlite3
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name, email FROM users WHERE id = ?",
            (user_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return f"User: {result[0]}, Email: {result[1]}"
        else:
            return f"User {user_id} not found"
    except Exception as e:
        return f"Error: {str(e)}"
```

## Next Steps

- [Add memory](04-agents-with-memory.md)
- [Test agents](05-testing-agents.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
