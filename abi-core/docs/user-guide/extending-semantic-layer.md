# Extending the Semantic Layer

## Overview

The semantic layer in ABI-Core is built on FastMCP and can be extended with custom tools, resources, and routes. This guide shows you how to add new functionality to enhance agent discovery and coordination.

## Semantic Layer Architecture

```
services/semantic_layer/
└── layer/
    ├── mcp_server/
    │   ├── server.py           # Main MCP server (extend here)
    │   ├── agent_cards/        # Agent metadata
    │   └── semantic_access_validator.py
    └── embedding_mesh/
        ├── api.py              # REST API routes
        ├── embeddings_abi.py   # Embedding generation
        └── weaviate_store.py   # Vector storage
```

## Built-in Tools

The semantic layer comes with these tools out of the box:

### 1. `find_agent`
Finds the best matching agent by natural language query using semantic search.

### 2. `recommend_agents` ✨ NEW
Recommends multiple agents for complex tasks with relevance scores.

### 3. `check_agent_capability` ✨ NEW
Checks if an agent has specific capabilities/tasks.

### 4. `check_agent_health` ✨ NEW
Checks if an agent is online and responding (with response time).

### 5. `get_agent_cards` (resource)
Retrieves all agent cards.

### 6. `get_agent_card` (resource)
Retrieves a specific agent card.

## Built-in Features

### Multi-Field Embeddings ✨ NEW
Agent cards are embedded using multiple fields for richer semantic matching:
- Agent name
- Agent description
- Supported tasks
- Skills descriptions

This is enabled by default and provides better agent discovery accuracy.

### Quota Management ✨ NEW
Built-in quota system to prevent abuse:
- Default: 1000 requests per agent per day
- Configurable via `SEMANTIC_LAYER_DAILY_QUOTA` environment variable
- Automatic reset every 24 hours
- In-memory tracking with LRU cache

## Using Built-in Tools

### Example 1: Agent Recommendation (Built-in) ✨

The `recommend_agents` tool is already implemented and ready to use:

**Python Usage:**
```python
from abi_core.common.semantic_tools import tool_recommend_agents

# Recommend agents for a complex task
recommendations = await tool_recommend_agents(
    task_description="Analyze market data and execute trades",
    max_agents=3
)

for rec in recommendations:
    agent = rec['agent']
    print(f"Agent: {agent['name']}")
    print(f"Relevance: {rec['relevance_score']:.2f}")
    print(f"Confidence: {rec['confidence']}")
```

**Direct MCP Call:**
```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
import json

async def get_recommendations():
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        result = await session.call_tool(
            name='recommend_agents',
            arguments={
                'task_description': 'Analyze market data and execute trades',
                'max_agents': 3
            }
        )
        
        recommendations = json.loads(result.content[0].text)
        return recommendations
```

**Implementation Details:**

The tool is implemented in `services/semantic_layer/layer/mcp_server/server.py`:

```python
@mcp.tool(
    name='recommend_agents',
    description='Recommends multiple agents for a complex task'
)
@validate_semantic_access
def recommend_agents(
    task_description: str,
    max_agents: int = 3,
    _request_context: dict = None
) -> list[dict]:
    """
    Recommend multiple agents for a complex task.
    
    Args:
        task_description: Description of the task
        max_agents: Maximum number of agents to recommend
        
    Returns:
        List of recommended agent cards with relevance scores
    """
    abi_logging(f"[🔍] Recommending agents for: {task_description}")
    
    if df is None or df.empty:
        abi_logging("[⚠️] No Agent Cards available")
        return []
    
    # Generate embedding for task
    query_embedding = embed_one(task_description)
    
    # Search for top matches
    results = search_agent_cards(
        query_vector=query_embedding,
        top_k=max_agents
    )
    
    # Format results with scores
    recommendations = []
    for result in results:
        agent_card = result["text"]
        score = result.get("score", 0.0)
        
        recommendations.append({
            "agent": agent_card,
            "relevance_score": score,
            "confidence": "high" if score > 0.8 else "medium" if score > 0.5 else "low"
        })
    
    abi_logging(f"[✅] Recommended {len(recommendations)} agents")
    return recommendations
```

**Usage:**
```python
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
import json

async def get_recommendations():
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        result = await session.call_tool(
            name='recommend_agents',
            arguments={
                'task_description': 'Analyze market data and execute trades',
                'max_agents': 3
            }
        )
        
        recommendations = json.loads(result.content[0].text)
        for rec in recommendations:
            print(f"Agent: {rec['agent']['name']}")
            print(f"Score: {rec['relevance_score']}")
            print(f"Confidence: {rec['confidence']}")
```

### Example 2: Agent Capability Check (Built-in) ✨

The `check_agent_capability` tool is already implemented:

**Python Usage:**
```python
from abi_core.common.semantic_tools import tool_check_agent_capability

# Check if agent has required capabilities
result = await tool_check_agent_capability(
    agent_name="trader",
    required_tasks=["execute_trade", "cancel_order", "get_portfolio"]
)

if result['has_all_capabilities']:
    print(f"✅ Agent has all required capabilities")
    print(f"Coverage: {result['capability_coverage']:.0%}")
else:
    print(f"❌ Missing: {result['missing_tasks']}")
```

**Implementation:**

```python
@mcp.tool(
    name='check_agent_capability',
    description='Check if an agent has specific capabilities'
)
@validate_semantic_access
def check_agent_capability(
    agent_name: str,
    required_tasks: list[str],
    _request_context: dict = None
) -> dict:
    """
    Check if an agent supports required tasks.
    
    Args:
        agent_name: Name of the agent to check
        required_tasks: List of required task names
        
    Returns:
        Capability check result with supported/missing tasks
    """
    abi_logging(f"[🔍] Checking capabilities for: {agent_name}")
    
    if df is None or df.empty:
        return {
            "agent": agent_name,
            "found": False,
            "error": "No agents available"
        }
    
    # Find agent card
    agent_cards = df[df['agent_card'].apply(
        lambda x: x.get('name', '').lower() == agent_name.lower()
    )]
    
    if agent_cards.empty:
        return {
            "agent": agent_name,
            "found": False,
            "error": "Agent not found"
        }
    
    agent_card = agent_cards.iloc[0]['agent_card']
    supported_tasks = agent_card.get('supportedTasks', [])
    
    # Check capabilities
    supported = [task for task in required_tasks if task in supported_tasks]
    missing = [task for task in required_tasks if task not in supported_tasks]
    
    return {
        "agent": agent_name,
        "found": True,
        "supported_tasks": supported,
        "missing_tasks": missing,
        "has_all_capabilities": len(missing) == 0,
        "capability_coverage": len(supported) / len(required_tasks) if required_tasks else 1.0
    }
```

**Usage:**
```python
async def check_capabilities():
    result = await session.call_tool(
        name='check_agent_capability',
        arguments={
            'agent_name': 'trader',
            'required_tasks': ['execute_trade', 'cancel_order', 'get_portfolio']
        }
    )
    
    check = json.loads(result.content[0].text)
    if check['has_all_capabilities']:
        print(f"✅ Agent has all required capabilities")
    else:
        print(f"❌ Missing: {check['missing_tasks']}")
```

### Example 3: Agent Health Check (Built-in) ✨

The `check_agent_health` tool is already implemented with 5-second timeout:

**Python Usage:**
```python
from abi_core.common.semantic_tools import tool_check_agent_health

# Check agent health
health = await tool_check_agent_health(agent_name="trader")

print(f"Status: {health['status']}")
if health['status'] == 'healthy':
    print(f"Response time: {health['response_time_ms']}ms")
else:
    print(f"Error: {health.get('error', 'Unknown')}")
```

**Implementation:**

```python
import httpx

@mcp.tool(
    name='check_agent_health',
    description='Check if an agent is online and responding'
)
@validate_semantic_access
async def check_agent_health(
    agent_name: str,
    _request_context: dict = None
) -> dict:
    """
    Check agent health status.
    
    Args:
        agent_name: Name of the agent to check
        
    Returns:
        Health status with response time
    """
    abi_logging(f"[🏥] Checking health for: {agent_name}")
    
    if df is None or df.empty:
        return {
            "agent": agent_name,
            "status": "unknown",
            "error": "No agents available"
        }
    
    # Find agent card
    agent_cards = df[df['agent_card'].apply(
        lambda x: x.get('name', '').lower() == agent_name.lower()
    )]
    
    if agent_cards.empty:
        return {
            "agent": agent_name,
            "status": "not_found",
            "error": "Agent not found"
        }
    
    agent_card = agent_cards.iloc[0]['agent_card']
    agent_url = agent_card.get('url', '')
    
    # Check health endpoint
    try:
        import time
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{agent_url}/health")
            
        response_time = (time.time() - start_time) * 1000  # ms
        
        return {
            "agent": agent_name,
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "url": agent_url,
            "response_time_ms": round(response_time, 2),
            "status_code": response.status_code
        }
        
    except httpx.TimeoutException:
        return {
            "agent": agent_name,
            "status": "timeout",
            "url": agent_url,
            "error": "Health check timeout"
        }
    except Exception as e:
        return {
            "agent": agent_name,
            "status": "error",
            "url": agent_url,
            "error": str(e)
        }
```

## Adding Custom Resources

Resources provide read-only data access via URIs.

### Example: Agent Statistics Resource

```python
@mcp.resource(
    'resource://agent_cards/statistics',
    mime_type='application/json'
)
@validate_semantic_access
def get_agent_statistics(_request_context: dict = None) -> dict:
    """
    Get statistics about registered agents.
    
    Returns:
        Statistics including agent count, task distribution, etc.
    """
    abi_logging("[📊] Generating agent statistics")
    
    if df is None or df.empty:
        return {
            "total_agents": 0,
            "error": "No agents available"
        }
    
    # Collect statistics
    total_agents = len(df)
    
    # Task distribution
    all_tasks = []
    for _, row in df.iterrows():
        agent_card = row['agent_card']
        tasks = agent_card.get('supportedTasks', [])
        all_tasks.extend(tasks)
    
    from collections import Counter
    task_counts = Counter(all_tasks)
    
    # Model distribution
    models = []
    for _, row in df.iterrows():
        agent_card = row['agent_card']
        model = agent_card.get('llmConfig', {}).get('model', 'unknown')
        models.append(model)
    
    model_counts = Counter(models)
    
    return {
        "total_agents": total_agents,
        "total_unique_tasks": len(task_counts),
        "most_common_tasks": dict(task_counts.most_common(5)),
        "model_distribution": dict(model_counts),
        "agent_names": [row['agent_card'].get('name') for _, row in df.iterrows()]
    }
```

**Usage:**
```python
async def get_stats():
    result = await session.read_resource('resource://agent_cards/statistics')
    stats = json.loads(result.contents[0].text)
    
    print(f"Total agents: {stats['total_agents']}")
    print(f"Most common tasks: {stats['most_common_tasks']}")
```

## Adding Custom REST Routes

Extend the embedding mesh API with custom routes.

**File:** `services/semantic_layer/layer/embedding_mesh/api.py`

### Example: Batch Agent Search

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class BatchSearchRequest(BaseModel):
    queries: list[str]
    max_results_per_query: int = 1

class BatchSearchResponse(BaseModel):
    results: list[dict]

@router.post("/v1/batch_search", response_model=BatchSearchResponse)
async def batch_search_agents(request: BatchSearchRequest):
    """
    Search for multiple agents in a single request.
    
    Args:
        queries: List of search queries
        max_results_per_query: Max results per query
        
    Returns:
        Batch search results
    """
    from layer.embedding_mesh.embeddings_abi import embed_one
    from layer.embedding_mesh.weaviate_store import search_agent_cards
    
    results = []
    
    for query in request.queries:
        # Generate embedding
        query_embedding = embed_one(query)
        
        # Search
        matches = search_agent_cards(
            query_vector=query_embedding,
            top_k=request.max_results_per_query
        )
        
        results.append({
            "query": query,
            "matches": matches
        })
    
    return BatchSearchResponse(results=results)
```

**Register route:**
```python
# In api.py
def attach_embedding_mesh_routes(app):
    """Attach embedding mesh routes to FastAPI app"""
    app.include_router(router, prefix="/api")
```

**Usage:**
```bash
curl -X POST http://localhost:8765/api/v1/batch_search \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      "agent for trading",
      "agent for analysis",
      "agent for risk management"
    ],
    "max_results_per_query": 2
  }'
```

## Advanced: Embedding Strategies

### Multi-field Embedding (Built-in) ✨

Multi-field embeddings are **enabled by default** in ABI-Core. The system automatically combines multiple fields for richer semantic matching:

**Fields Combined:**
- Agent name
- Agent description
- Supported tasks
- Skills descriptions

**Implementation:**

The default implementation in `services/semantic_layer/layer/embedding_mesh/embeddings_abi.py`:

```python
def build_agent_card_embeddings(force_reload: bool = False) -> Optional[pd.DataFrame]:
    """Generates embeddings using multi-field strategy (default)."""
    
    # ... load agent cards ...
    
    # Multi-field embedding strategy (default)
    def create_combined_text(card: dict) -> str:
        """Combine multiple fields for richer embedding."""
        parts = [
            card.get('name', ''),
            card.get('description', ''),
            ' '.join(card.get('supportedTasks', [])),
            ' '.join([
                skill.get('description', '') 
                for skill in card.get('skills', [])
            ])
        ]
        return ' '.join(filter(None, parts))
    
    df['combined_text'] = df['agent_card'].apply(create_combined_text)
    df['card_embeddings'] = df['combined_text'].apply(embed_one)
    
    return df
```

**Benefits:**
- Better semantic matching accuracy
- Considers agent capabilities holistically
- Improved discovery for complex queries
- No configuration needed - works out of the box

## Semantic Access Policies

### Quota Management (Built-in) ✨

Quota management is **built-in** and enabled by default to prevent abuse:

**Features:**
- Default limit: 1000 requests per agent per day
- Automatic reset every 24 hours
- In-memory tracking with LRU cache (no Redis required)
- Configurable via environment variable

**Configuration:**

```bash
# Set custom daily quota (default: 1000)
export SEMANTIC_LAYER_DAILY_QUOTA=5000
```

**Implementation:**

The quota system is integrated in `src/abi_core/semantic/semantic_access_validator.py`:

```python
class QuotaManager:
    """Manages agent usage quotas with in-memory tracking"""
    
    def __init__(self, daily_limit: int = 1000):
        self.daily_limit = daily_limit
        self.usage = defaultdict(lambda: {"count": 0, "reset_time": None})
    
    def check_and_increment(self, agent_id: str) -> Dict[str, Any]:
        """Check if agent is within quota and increment usage."""
        now = datetime.utcnow()
        agent_usage = self.usage[agent_id]
        
        # Reset if past reset time
        if agent_usage["reset_time"] is None or now >= agent_usage["reset_time"]:
            agent_usage["count"] = 0
            agent_usage["reset_time"] = now + timedelta(days=1)
        
        # Check quota
        if agent_usage["count"] >= self.daily_limit:
            return {
                "allowed": False,
                "current_usage": agent_usage["count"],
                "limit": self.daily_limit,
                "reset_time": agent_usage["reset_time"].isoformat()
            }
        
        # Increment usage
        agent_usage["count"] += 1
        return {"allowed": True, ...}

# Global quota manager
_quota_manager = QuotaManager(
    daily_limit=int(os.getenv("SEMANTIC_LAYER_DAILY_QUOTA", "1000"))
)
```

**Quota Response:**

When quota is exceeded, agents receive:

```json
{
  "allowed": false,
  "reason": "Daily quota exceeded (1000/1000)",
  "error_code": "QUOTA_EXCEEDED",
  "risk_score": 0.8,
  "quota_info": {
    "current_usage": 1000,
    "limit": 1000,
    "reset_time": "2025-01-22T00:00:00"
  }
}
```

### Adding Custom Policies

You can still add custom validation decorators for additional rules:

```python
from functools import wraps

def validate_business_hours(func):
    """Only allow access during business hours"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from datetime import datetime
        hour = datetime.utcnow().hour
        
        if hour < 9 or hour >= 17:
            return {
                "error": "Access only allowed during business hours (9 AM - 5 PM UTC)"
            }
        
        return await func(*args, **kwargs)
    
    return wrapper

# Use with tools
@mcp.tool(name='find_agent')
@validate_business_hours
@validate_semantic_access
def find_agent(query: str, _request_context: dict = None):
    # ... implementation
    pass
```

## Testing Custom Extensions

### Unit Tests

```python
# tests/test_semantic_layer_extensions.py
import pytest
from layer.mcp_server.server import recommend_agents

@pytest.mark.asyncio
async def test_recommend_agents():
    """Test agent recommendation tool"""
    result = recommend_agents(
        task_description="Execute stock trades",
        max_agents=3
    )
    
    assert isinstance(result, list)
    assert len(result) <= 3
    assert all('agent' in rec for rec in result)
    assert all('relevance_score' in rec for rec in result)

@pytest.mark.asyncio
async def test_check_agent_capability():
    """Test capability checking"""
    result = check_agent_capability(
        agent_name="trader",
        required_tasks=["execute_trade", "cancel_order"]
    )
    
    assert result['found'] == True
    assert result['has_all_capabilities'] == True
```

### Integration Tests

```python
# tests/integration/test_mcp_tools.py
import pytest
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

@pytest.mark.asyncio
async def test_custom_tool_integration():
    """Test custom tool via MCP"""
    config = get_mcp_server_config()
    
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Test recommend_agents tool
        result = await session.call_tool(
            name='recommend_agents',
            arguments={
                'task_description': 'Analyze market data',
                'max_agents': 2
            }
        )
        
        assert result.content is not None
```

## Best Practices

### 1. Always Use Access Validation

```python
# ✅ Good
@mcp.tool(name='my_tool')
@validate_semantic_access
def my_tool(query: str, _request_context: dict = None):
    pass

# ❌ Bad
@mcp.tool(name='my_tool')
def my_tool(query: str):
    pass  # No access control
```

### 2. Include Request Context

```python
# ✅ Good
def my_tool(query: str, _request_context: dict = None):
    agent_id = _request_context.get('headers', {}).get('X-ABI-Agent-ID')
    # Use agent_id for logging, quotas, etc.

# ❌ Bad
def my_tool(query: str):
    # Can't identify requesting agent
    pass
```

### 3. Log Operations

```python
# ✅ Good
from abi_core.common.utils import abi_logging

def my_tool(query: str, _request_context: dict = None):
    abi_logging(f"[🔧] Processing: {query}")
    result = process(query)
    abi_logging(f"[✅] Completed: {result}")
    return result
```

### 4. Handle Errors Gracefully

```python
# ✅ Good
def my_tool(query: str, _request_context: dict = None):
    try:
        return process(query)
    except Exception as e:
        abi_logging(f"[❌] Error: {e}", "error")
        return {
            "error": str(e),
            "query": query
        }
```

### 5. Document Tools

```python
# ✅ Good
@mcp.tool(
    name='my_tool',
    description='Clear description of what the tool does'
)
def my_tool(query: str, _request_context: dict = None) -> dict:
    """
    Detailed docstring explaining:
    - What the tool does
    - Parameters
    - Return value
    - Examples
    """
    pass
```

## Deployment

After adding extensions, rebuild and restart:

```bash
# Rebuild semantic layer
docker-compose build semantic-layer

# Restart service
docker-compose restart semantic-layer

# Check logs
docker-compose logs -f semantic-layer
```

## Next Steps

- [Complete Example](complete-example.md) - See semantic layer in action
- [Agent Development](agent-development.md) - Build agents that use custom tools
- [Policy Development](policy-development.md) - Add access policies

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
