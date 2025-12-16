# Complete Example: Building a Multi-Agent System

This guide walks you through creating a complete ABI-Core project with agents, semantic layer, agent cards, and security policies.

## What We'll Build

A financial analysis system with:
- **3 specialized agents** (Trader, Analyst, Risk Manager)
- **Semantic layer** for agent discovery
- **Agent cards** for capability metadata
- **Guardian service** for security and policies

## Prerequisites

```bash
# Ensure you have ABI-Core installed
pip install abi-core-ai

# Verify installation
abi-core --version

# Ensure Ollama is running
ollama serve
```

## Step 1: Create the Project

Create a new project with semantic layer and guardian:

```bash
# Create project with centralized model serving (recommended)
abi-core create project fintech-ai \
  --domain finance \
  --with-semantic-layer \
  --with-guardian \
  --model-serving centralized

# Navigate to project
cd fintech-ai
```

**What this creates:**
```
fintech-ai/
├── agents/                 # Agents directory (empty initially)
├── services/
│   ├── semantic_layer/     # Agent discovery service
│   │   └── layer/
│   │       ├── mcp_server/         # MCP server for agent communication
│   │       │   └── agent_cards/    # Agent cards directory
│   │       └── embedding_mesh/     # Vector embeddings
│   └── guardian/           # Security service
│       ├── agent/          # Guardian agent code
│       └── opa/            # OPA policies
│           └── policies/   # Policy files (.rego)
├── compose.yaml            # Docker orchestration
├── .abi/
│   └── runtime.yaml        # Project configuration
└── README.md
```

## Step 2: Provision Models

Download and configure LLM models automatically:

```bash
# This command will:
# 1. Start the centralized Ollama service
# 2. Download qwen2.5:3b (LLM model)
# 3. Download nomic-embed-text:v1.5 (embedding model)
# 4. Update runtime.yaml with status
abi-core provision-models
```

**Output:**
```
🚀 Starting model provisioning...
📦 Model serving mode: centralized
🔄 Starting Ollama service...
✅ Ollama service started
📥 Downloading qwen2.5:3b...
✅ qwen2.5:3b downloaded successfully
📥 Downloading nomic-embed-text:v1.5...
✅ nomic-embed-text:v1.5 downloaded successfully
✅ Models provisioned successfully
```

## Step 3: Create Specialized Agents

### 3.1 Create Trader Agent

```bash
abi-core add agent trader \
  --description "Executes trading operations and order management" \
  --model qwen2.5:3b
```

**Generated files:**
```
agents/trader/
├── __init__.py
├── agent_trader.py      # Agent implementation
├── main.py              # Entry point
├── models.py            # Data models
├── Dockerfile           # Container config
└── requirements.txt     # Dependencies
```

### 3.2 Create Analyst Agent

```bash
abi-core add agent analyst \
  --description "Performs market analysis and generates insights" \
  --model qwen2.5:3b
```

### 3.3 Create Risk Manager Agent

```bash
abi-core add agent risk_manager \
  --description "Evaluates risk and compliance for trading operations" \
  --model qwen2.5:3b
```

## Step 4: Create Agent Cards

Agent cards enable semantic discovery. Create one for each agent:

### 4.1 Trader Agent Card

```bash
abi-core add agent-card trader \
  --description "Executes trading operations including buy, sell, and order management" \
  --url "http://trader-agent:8000" \
  --tasks "execute_trade,cancel_order,check_position,get_portfolio"
```

**Generated file:** `services/semantic_layer/layer/mcp_server/agent_cards/trader.json`

```json
{
  "@context": ["https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"],
  "@type": "Agent",
  "id": "agent://trader",
  "name": "trader",
  "description": "Executes trading operations including buy, sell, and order management",
  "url": "http://trader-agent:8000",
  "version": "1.0.0",
  "capabilities": {
    "streaming": "True",
    "pushNotifications": "True",
    "stateTransitionHistory": "False"
  },
  "supportedTasks": [
    "execute_trade",
    "cancel_order",
    "check_position",
    "get_portfolio"
  ],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "temperature": 0.1
  },
  "skills": [
    {
      "id": "execute_trade",
      "name": "Execute Trade",
      "description": "Execute trading operations",
      "tags": ["trading", "execution", "orders"],
      "examples": ["Buy 100 shares of AAPL", "Sell 50 shares of GOOGL"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ]
}
```

### 4.2 Analyst Agent Card

```bash
abi-core add agent-card analyst \
  --description "Performs market analysis, technical analysis, and generates trading insights" \
  --url "http://analyst-agent:8001" \
  --tasks "analyze_market,technical_analysis,generate_report,predict_trend"
```

### 4.3 Risk Manager Agent Card

```bash
abi-core add agent-card risk_manager \
  --description "Evaluates risk, checks compliance, and validates trading operations" \
  --url "http://risk-manager-agent:8002" \
  --tasks "evaluate_risk,check_compliance,validate_trade,calculate_exposure"
```

## Step 5: Start the System

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

**Running services:**
```
NAME                          STATUS    PORTS
fintech-ai-ollama             Up        0.0.0.0:11434->11434/tcp
trader-agent                  Up        0.0.0.0:8000->8000/tcp
analyst-agent                 Up        0.0.0.0:8001->8001/tcp
risk-manager-agent            Up        0.0.0.0:8002->8002/tcp
semantic-layer                Up        0.0.0.0:8765->8765/tcp
guardian                      Up        0.0.0.0:11438->11438/tcp
guardian-opa                  Up        0.0.0.0:8181->8181/tcp
weaviate                      Up        0.0.0.0:8080->8080/tcp
```

## Step 6: Using the Semantic Layer

### 6.1 Find Agent by Capability

Use the `find_agent` tool to discover agents:

**Python Example:**
```python
import asyncio
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config

async def find_trading_agent():
    """Find an agent capable of executing trades"""
    
    # Get MCP server configuration
    config = get_mcp_server_config()
    
    # Connect to semantic layer
    async with client.init_session(
        config.host,
        config.port,
        config.transport
    ) as session:
        # Find agent using natural language
        result = await client.find_agent(
            session,
            "Find an agent that can execute stock trades"
        )
        
        # Parse result
        if result.content:
            import json
            agent_card = json.loads(result.content[0].text)
            print(f"Found agent: {agent_card['name']}")
            print(f"URL: {agent_card['url']}")
            print(f"Tasks: {agent_card['supportedTasks']}")
            return agent_card
        
        return None

# Run
agent = asyncio.run(find_trading_agent())
```

**Output:**
```
Found agent: trader
URL: http://trader-agent:8000
Tasks: ['execute_trade', 'cancel_order', 'check_position', 'get_portfolio']
```

### 6.2 HTTP API Example

Query the semantic layer via HTTP:

```bash
# Find agent for market analysis
curl -X POST http://localhost:8765/v1/tools/find_agent \
  -H "Content-Type: application/json" \
  -H "X-ABI-Agent-ID: agent://client" \
  -d '{
    "query": "Find an agent that can analyze market trends"
  }'
```

**Response:**
```json
{
  "@type": "Agent",
  "id": "agent://analyst",
  "name": "analyst",
  "description": "Performs market analysis, technical analysis, and generates trading insights",
  "url": "http://analyst-agent:8001",
  "supportedTasks": [
    "analyze_market",
    "technical_analysis",
    "generate_report",
    "predict_trend"
  ]
}
```

### 6.3 List All Agents

```bash
# Get all registered agents
curl http://localhost:8765/v1/agents
```

**Response:**
```json
{
  "agents": [
    {
      "id": "agent://trader",
      "name": "trader",
      "url": "http://trader-agent:8000",
      "status": "active"
    },
    {
      "id": "agent://analyst",
      "name": "analyst",
      "url": "http://analyst-agent:8001",
      "status": "active"
    },
    {
      "id": "agent://risk_manager",
      "name": "risk_manager",
      "url": "http://risk-manager-agent:8002",
      "status": "active"
    }
  ]
}
```

## Step 7: Interacting with Agents

### 7.1 Direct Agent Communication

Query an agent directly:

```bash
# Ask trader agent to execute a trade
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Buy 100 shares of AAPL at market price",
    "context_id": "trade-001",
    "task_id": "task-001"
  }'
```

### 7.2 Agent-to-Agent Communication (A2A)

Agents can communicate with each other:

**Example: Trader asks Risk Manager for approval**

```python
# In trader agent code
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams

async def execute_trade_with_risk_check(trade_details):
    """Execute trade after risk validation"""
    
    # Find risk manager agent
    risk_manager_card = await find_agent("risk management agent")
    
    # Create A2A client
    async with httpx.AsyncClient() as http_client:
        a2a_client = A2AClient(http_client, risk_manager_card)
        
        # Ask for risk evaluation
        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{
                        'kind': 'text',
                        'text': f"Evaluate risk for trade: {trade_details}"
                    }],
                    'messageId': 'risk-check-001',
                    'contextId': 'trade-001'
                }
            )
        )
        
        # Get risk assessment
        async for response in a2a_client.send_message_stream(request):
            if response.root.result.artifact:
                risk_assessment = response.root.result.artifact
                
                if risk_assessment['approved']:
                    # Execute trade
                    return await self.execute_trade(trade_details)
                else:
                    return {
                        'status': 'rejected',
                        'reason': risk_assessment['reason']
                    }
```

## Step 8: Security with Guardian

### 8.1 View Guardian Dashboard

Access the security dashboard:

```bash
# Open in browser
open http://localhost:8080
```

**Dashboard shows:**
- Active agents and their status
- Policy evaluation metrics
- Security alerts
- Audit logs
- Risk scores

### 8.2 Add Custom Policies

Create a custom policy for trading limits:

**File:** `services/guardian/opa/policies/trading_limits.rego`

```rego
package abi.trading

import future.keywords.if
import future.keywords.in

# Default deny
default allow = false

# Allow trades under $10,000
allow if {
    input.action == "execute_trade"
    input.trade_amount < 10000
}

# Require approval for large trades
require_approval if {
    input.action == "execute_trade"
    input.trade_amount >= 10000
    input.trade_amount < 100000
}

# Deny very large trades
deny["Trade amount exceeds maximum limit"] if {
    input.action == "execute_trade"
    input.trade_amount >= 100000
}

# Calculate risk score
risk_score = score if {
    input.trade_amount < 10000
    score := 0.1
}

risk_score = score if {
    input.trade_amount >= 10000
    input.trade_amount < 100000
    score := 0.5
}

risk_score = score if {
    input.trade_amount >= 100000
    score := 1.0
}
```

### 8.3 Test Policy

```bash
# Test policy via OPA API
curl -X POST http://localhost:8181/v1/data/abi/trading \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "execute_trade",
      "trade_amount": 5000,
      "agent_id": "agent://trader"
    }
  }'
```

**Response:**
```json
{
  "result": {
    "allow": true,
    "require_approval": false,
    "deny": [],
    "risk_score": 0.1
  }
}
```

## Step 9: Complete Workflow Example

Here's a complete workflow combining all components:

```python
import asyncio
import httpx
from abi_core.abi_mcp import client
from abi_core.common.utils import get_mcp_server_config
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendStreamingMessageRequest
from uuid import uuid4

async def execute_validated_trade(trade_request):
    """
    Complete workflow:
    1. Find appropriate agents via semantic layer
    2. Get risk assessment from risk manager
    3. Execute trade if approved
    4. Generate analysis report
    """
    
    print("Step 1: Finding agents via semantic layer...")
    config = get_mcp_server_config()
    
    async with client.init_session(config.host, config.port, config.transport) as session:
        # Find trader agent
        trader_result = await client.find_agent(session, "agent that executes trades")
        trader_card = AgentCard(**json.loads(trader_result.content[0].text))
        print(f"✅ Found trader: {trader_card.name}")
        
        # Find risk manager
        risk_result = await client.find_agent(session, "agent that evaluates risk")
        risk_card = AgentCard(**json.loads(risk_result.content[0].text))
        print(f"✅ Found risk manager: {risk_card.name}")
        
        # Find analyst
        analyst_result = await client.find_agent(session, "agent that analyzes markets")
        analyst_card = AgentCard(**json.loads(analyst_result.content[0].text))
        print(f"✅ Found analyst: {analyst_card.name}")
    
    print("\nStep 2: Getting risk assessment...")
    async with httpx.AsyncClient() as http_client:
        risk_client = A2AClient(http_client, risk_card)
        
        risk_request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{
                        'kind': 'text',
                        'text': f"Evaluate risk for: {trade_request}"
                    }],
                    'messageId': 'risk-001',
                    'contextId': 'trade-workflow-001'
                }
            )
        )
        
        risk_approved = False
        async for response in risk_client.send_message_stream(risk_request):
            if hasattr(response.root.result, 'artifact'):
                risk_result = response.root.result.artifact
                risk_approved = risk_result.get('approved', False)
                print(f"Risk assessment: {'✅ Approved' if risk_approved else '❌ Rejected'}")
                break
        
        if not risk_approved:
            print("❌ Trade rejected by risk manager")
            return {'status': 'rejected', 'reason': 'Risk assessment failed'}
        
        print("\nStep 3: Executing trade...")
        trader_client = A2AClient(http_client, trader_card)
        
        trade_request_msg = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{
                        'kind': 'text',
                        'text': trade_request
                    }],
                    'messageId': 'trade-001',
                    'contextId': 'trade-workflow-001'
                }
            )
        )
        
        trade_result = None
        async for response in trader_client.send_message_stream(trade_request_msg):
            if hasattr(response.root.result, 'artifact'):
                trade_result = response.root.result.artifact
                print(f"✅ Trade executed: {trade_result}")
                break
        
        print("\nStep 4: Generating analysis report...")
        analyst_client = A2AClient(http_client, analyst_card)
        
        analysis_request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message={
                    'role': 'user',
                    'parts': [{
                        'kind': 'text',
                        'text': f"Analyze the impact of trade: {trade_result}"
                    }],
                    'messageId': 'analysis-001',
                    'contextId': 'trade-workflow-001'
                }
            )
        )
        
        async for response in analyst_client.send_message_stream(analysis_request):
            if hasattr(response.root.result, 'artifact'):
                analysis = response.root.result.artifact
                print(f"✅ Analysis complete: {analysis}")
                break
        
        return {
            'status': 'success',
            'trade': trade_result,
            'analysis': analysis
        }

# Run the workflow
if __name__ == "__main__":
    trade = "Buy 100 shares of AAPL at market price"
    result = asyncio.run(execute_validated_trade(trade))
    print(f"\n{'='*60}")
    print("Final Result:")
    print(f"{'='*60}")
    print(result)
```

**Output:**
```
Step 1: Finding agents via semantic layer...
✅ Found trader: trader
✅ Found risk manager: risk_manager
✅ Found analyst: analyst

Step 2: Getting risk assessment...
Risk assessment: ✅ Approved

Step 3: Executing trade...
✅ Trade executed: {'order_id': 'ORD-12345', 'status': 'filled', 'shares': 100}

Step 4: Generating analysis report...
✅ Analysis complete: {'impact': 'positive', 'confidence': 0.85}

============================================================
Final Result:
============================================================
{
  'status': 'success',
  'trade': {'order_id': 'ORD-12345', 'status': 'filled', 'shares': 100},
  'analysis': {'impact': 'positive', 'confidence': 0.85}
}
```

## Step 10: Monitoring and Debugging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trader-agent
docker-compose logs -f semantic-layer
docker-compose logs -f guardian
```

### Check Agent Status

```bash
# Via semantic layer
curl http://localhost:8765/v1/agents

# Via guardian dashboard
curl http://localhost:8080/api/agents/status
```

### Monitor Policies

```bash
# Check OPA health
curl http://localhost:8181/health

# View policy decisions
curl http://localhost:8181/v1/data/abi
```

## Next Steps

- [Semantic Enrichment](semantic-enrichment.md) - Deep dive into semantic processing
- [Policy Development](policy-development.md) - Write custom security policies
- [Agent Development](agent-development.md) - Build advanced agents
- [Deployment](deployment.md) - Deploy to production

## Troubleshooting

### Agent Not Found

```bash
# Check if agent card exists
ls services/semantic_layer/layer/mcp_server/agent_cards/

# Restart semantic layer to reload cards
docker-compose restart semantic-layer
```

### Policy Errors

```bash
# Test policy syntax
docker exec guardian-opa opa test /app/opa/policies/

# View OPA logs
docker-compose logs guardian-opa
```

### Connection Issues

```bash
# Check network
docker network inspect fintech-ai-network

# Verify ports
docker-compose ps
```

## Summary

You've built a complete multi-agent system with:

✅ **3 specialized agents** with different capabilities  
✅ **Semantic layer** for intelligent agent discovery  
✅ **Agent cards** for capability metadata  
✅ **Guardian service** for security and policies  
✅ **Complete workflows** with agent-to-agent communication  

This architecture enables:
- Intelligent agent routing based on capabilities
- Secure inter-agent communication
- Policy-driven governance
- Scalable multi-agent orchestration
