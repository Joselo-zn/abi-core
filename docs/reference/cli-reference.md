# CLI Reference

Complete reference for all ABI-Core CLI commands.

## Overview

The `abi-core` CLI provides commands for creating, managing, and deploying AI agent systems.

```bash
abi-core [COMMAND] [OPTIONS]
```

## Global Options

```bash
--version          Show version and exit
--help            Show help message and exit
```

---

## Commands

### `create`

Create new ABI projects and components.

#### `create project`

Create a new ABI project with agents, services, and configuration.

**Syntax:**
```bash
abi-core create project <name> [OPTIONS]
```

**Options:**
- `--name, -n` (required) - Project name
- `--description, -d` - Project description
- `--domain` - Domain/industry (e.g., finance, healthcare, general)
- `--with-semantic-layer` - Include semantic layer service
- `--with-guardian` - Include Guardian security service
- `--model-serving` - Model serving strategy: `centralized` or `distributed`

**Examples:**
```bash
# Basic project
abi-core create project my-app

# Project with semantic layer
abi-core create project my-app --with-semantic-layer

# Complete project with all services
abi-core create project fintech-ai \
  --domain finance \
  --with-semantic-layer \
  --with-guardian \
  --model-serving centralized

# Project with description
abi-core create project my-app \
  --description "My AI agent system" \
  --domain general
```

**What it creates:**
```
my-app/
├── agents/              # Agents directory
├── services/            # Services directory
│   ├── semantic_layer/  # (if --with-semantic-layer)
│   └── guardian/        # (if --with-guardian)
├── compose.yaml         # Docker orchestration
├── .abi/
│   └── runtime.yaml     # Project configuration
└── README.md
```

---

### `add`

Add components to existing ABI project.

#### `add agent`

Add a new agent to the project.

**Syntax:**
```bash
abi-core add agent <name> [OPTIONS]
```

**Options:**
- `--name, -n` (required) - Agent name
- `--description, -d` - Agent description
- `--model` - LLM model (default: `qwen2.5:3b`)
- `--with-web-interface` - Include web interface

**Examples:**
```bash
# Basic agent
abi-core add agent my-agent

# Agent with description
abi-core add agent trader \
  --description "Executes trading operations"

# Agent with custom model
abi-core add agent analyst \
  --description "Market analysis agent" \
  --model mistral:7b

# Agent with web interface
abi-core add agent assistant \
  --description "AI assistant" \
  --with-web-interface
```

**What it creates:**
```
agents/my-agent/
├── __init__.py
├── agent_my_agent.py    # Agent implementation
├── main.py              # Entry point
├── models.py            # Data models
├── Dockerfile
└── requirements.txt
```

#### `add agent-card`

Create an agent card for semantic layer registration.

**Syntax:**
```bash
abi-core add agent-card <name> [OPTIONS]
```

**Options:**
- `--name, -n` (required) - Agent name
- `--description, -d` - Agent description
- `--model` - LLM model (default: `qwen2.5:3b`)
- `--url` - Agent URL (default: `http://localhost:8000`)
- `--tasks` - Comma-separated list of supported tasks

**Examples:**
```bash
# Basic agent card
abi-core add agent-card trader

# Complete agent card
abi-core add agent-card trader \
  --description "Executes trading operations" \
  --url "http://trader-agent:8000" \
  --tasks "execute_trade,cancel_order,check_position"

# Agent card with custom model
abi-core add agent-card analyst \
  --description "Market analysis" \
  --model mistral:7b \
  --url "http://analyst-agent:8001" \
  --tasks "analyze_market,generate_report"
```

**What it creates:**
```
services/semantic_layer/layer/mcp_server/agent_cards/trader.json
```

**Agent card structure:**
```json
{
  "@context": ["..."],
  "@type": "Agent",
  "id": "agent://trader",
  "name": "trader",
  "description": "Executes trading operations",
  "url": "http://trader-agent:8000",
  "supportedTasks": ["execute_trade", "cancel_order"],
  "llmConfig": {
    "provider": "ollama",
    "model": "qwen2.5:3b"
  }
}
```

#### `add service`

Add a service to the project.

**Syntax:**
```bash
abi-core add service <service-type> [OPTIONS]
```

**Service Types:**
- `semantic-layer` - Agent discovery and routing
- `guardian` - Security and policy enforcement

**Options:**
- `--name` - Service name (optional)
- `--domain` - Domain for policies (finance, healthcare, general)

**Examples:**
```bash
# Add semantic layer
abi-core add service semantic-layer

# Add guardian with domain
abi-core add service guardian --domain finance

# Add with custom name
abi-core add service semantic-layer --name my-semantic-layer
```

**Shortcuts:**
```bash
# Direct semantic layer addition
abi-core add semantic-layer

# Direct guardian addition
abi-core add guardian --domain finance
```

#### `add policies`

Add security policies to Guardian service.

**Syntax:**
```bash
abi-core add policies <name> [OPTIONS]
```

**Options:**
- `--name, -n` (required) - Policy name
- `--domain` - Domain (finance, healthcare, general)

**Examples:**
```bash
# Add trading policies
abi-core add policies trading --domain finance

# Add compliance policies
abi-core add policies compliance --domain healthcare
```

**What it creates:**
```
services/guardian/opa/policies/<name>.rego
```

#### `add agentic-orchestration-layer`

Add Planner and Orchestrator agents for multi-agent workflow coordination.

**Syntax:**
```bash
abi-core add agentic-orchestration-layer
```

**Prerequisites:**
- Guardian service must be configured
- Semantic layer service must be configured

**Examples:**
```bash
# Add orchestration layer
abi-core add agentic-orchestration-layer
```

**What it creates:**
```
agents/
├── planner/
│   ├── main.py
│   ├── planner.py
│   ├── agent_cards/
│   │   └── planner_agent.json
│   ├── Dockerfile
│   └── requirements.txt
└── orchestrator/
    ├── main.py
    ├── orchestrator.py
    ├── web_interface.py
    ├── agent_cards/
    │   └── orchestrator_agent.json
    ├── Dockerfile
    └── requirements.txt

services/semantic_layer/layer/mcp_server/agent_cards/
├── planner_agent.json
└── orchestrator_agent.json
```

**What it does:**

1. **Verifies prerequisites**: Checks for Guardian and Semantic Layer services
2. **Creates Planner Agent**: 
   - Decomposes complex queries into tasks
   - Assigns agents to tasks using semantic search
   - Creates execution plans with dependencies
   - Handles clarification questions
3. **Creates Orchestrator Agent**:
   - Coordinates multi-agent workflow execution
   - Performs health checks on assigned agents
   - Executes workflows with LangGraph
   - Synthesizes results from multiple agents
   - Provides web interface for HTTP/SSE access
4. **Generates signed agent cards**:
   - Creates unique authentication tokens
   - Includes full A2A protocol metadata
   - Registers with semantic layer automatically
5. **Updates configuration**:
   - Adds agents to `runtime.yaml`
   - Updates `compose.yaml` with services
   - Configures ports dynamically

**Agent Capabilities:**

**Planner Agent (port 11437):**
- Task decomposition with Chain of Thought reasoning
- Semantic agent discovery via MCP tools
- Clarification question generation
- Dependency management
- Execution strategy selection

**Orchestrator Agent (port 8002 A2A, 8083 Web):**
- Workflow execution with state management
- Agent health monitoring with retries
- Progress streaming every 5 seconds
- Result synthesis with LLM
- Q&A handling between agents

**Usage Example:**
```bash
# 1. Create project with prerequisites
abi-core create project my-system \
  --with-semantic-layer \
  --with-guardian

# 2. Add orchestration layer
abi-core add agentic-orchestration-layer

# 3. Start system
abi-core run

# 4. Send query to Orchestrator
curl -X POST http://localhost:8083/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "analyze customer data and generate report",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

**See Also:**
- [Planner + Orchestrator Integration Guide](planner-orchestrator-integration.md)
- [Multi-Agent Workflows](../getting-started/concepts.md#multi-agent-workflows)

---

### `remove`

Remove components from project.

#### `remove agent`

Remove an agent from the project.

**Syntax:**
```bash
abi-core remove agent <name>
```

**Examples:**
```bash
# Remove agent
abi-core remove agent my-agent

# Remove multiple agents
abi-core remove agent agent1
abi-core remove agent agent2
```

#### `remove service`

Remove a service from the project.

**Syntax:**
```bash
abi-core remove service <name>
```

**Examples:**
```bash
# Remove semantic layer
abi-core remove service semantic_layer

# Remove guardian
abi-core remove service guardian
```

---

### `provision-models`

Download and configure LLM models automatically.

**Syntax:**
```bash
abi-core provision-models [OPTIONS]
```

**Options:**
- `--force` - Force re-download even if models exist

**Examples:**
```bash
# Provision models (default)
abi-core provision-models

# Force re-download
abi-core provision-models --force
```

**What it does:**

**Centralized Mode:**
1. Starts main Ollama service
2. Downloads LLM model (qwen2.5:3b)
3. Downloads embedding model (nomic-embed-text:v1.5)
4. Updates runtime.yaml

**Distributed Mode:**
1. Starts each agent service
2. Downloads LLM to each agent's Ollama
3. Starts main Ollama for embeddings
4. Downloads embedding model
5. Updates runtime.yaml

**Output:**
```
🚀 my-project Model Provisioner
Mode: centralized
LLM: qwen2.5:3b
Embeddings: nomic-embed-text:v1.5
========================================

📦 CENTRALIZED MODE
-------------------
[14:30:15] 🚀 Starting service: my-project-ollama...
[14:30:18] ✅ Service my-project-ollama started
[14:30:23] ✅ Ollama ready in my-project-ollama
[14:30:23] ⬇️  Pulling 'qwen2.5:3b'...
[14:32:50] ✅ Model 'qwen2.5:3b' ready
[14:32:50] ⬇️  Pulling 'nomic-embed-text:v1.5'...
[14:33:17] ✅ Model 'nomic-embed-text:v1.5' ready

========================================
🎉 Model provisioning completed!
========================================
```

---

### `run`

Start the project services.

**Syntax:**
```bash
abi-core run [OPTIONS]
```

**Options:**
- `--mode` - Run mode: `dev`, `prod`, `test` (default: `dev`)
- `--detach, -d` - Run in background

**Examples:**
```bash
# Start in foreground
abi-core run

# Start in background
abi-core run --detach

# Start in production mode
abi-core run --mode prod

# Start in test mode
abi-core run --mode test
```

**What it does:**
```bash
# Equivalent to:
docker-compose up
```

---

### `status`

Check project and services status.

**Syntax:**
```bash
abi-core status
```

**Examples:**
```bash
# Check status
abi-core status
```

**Output:**
```
Project: my-project
Status: Running

Services:
  ✅ my-project-ollama (Up)
  ✅ trader-agent (Up)
  ✅ analyst-agent (Up)
  ✅ semantic-layer (Up)
  ✅ guardian (Up)

Agents:
  - trader (port: 8000)
  - analyst (port: 8001)

Model Serving: centralized
```

---

### `info`

Show project information.

**Syntax:**
```bash
abi-core info [COMPONENT]
```

**Components:**
- `agents` - List all agents
- `services` - List all services
- `policies` - List all policies

**Examples:**
```bash
# Show all info
abi-core info

# Show agents only
abi-core info agents

# Show services only
abi-core info services

# Show policies only
abi-core info policies
```

**Output:**
```
Project: my-project
Domain: finance
Model Serving: centralized

Agents (2):
  - trader (qwen2.5:3b) - port 8000
  - analyst (qwen2.5:3b) - port 8001

Services (2):
  - semantic_layer (port 8765)
  - guardian (port 11438)

Policies (3):
  - semantic_access.rego
  - trading_limits.rego
  - compliance.rego
```

---

## Configuration Files

### `.abi/runtime.yaml`

Project runtime configuration.

```yaml
project:
  name: "my-project"
  domain: "finance"
  model_serving: "centralized"
  default_model: "qwen2.5:3b"

agents:
  trader:
    model: "qwen2.5:3b"
    port: 8000
    ollama_host: "http://my-project-ollama:11434"
  analyst:
    model: "qwen2.5:3b"
    port: 8001
    ollama_host: "http://my-project-ollama:11434"

services:
  semantic_layer:
    port: 8765
    weaviate_host: "http://weaviate:8080"
  guardian:
    port: 11438
    opa_port: 8181

models:
  llm:
    name: "qwen2.5:3b"
    provisioned: true
  embedding:
    name: "nomic-embed-text:v1.5"
    provisioned: true
```

### `compose.yaml`

Docker Compose configuration (auto-generated).

---

## Environment Variables

### Global

```bash
# Logging
ABI_SETTINGS_LOGGING_DEBUG=true    # Enable debug logging

# Model serving
MODEL_NAME=qwen2.5:3b               # Default LLM model
OLLAMA_HOST=http://localhost:11434  # Ollama host
```

### Semantic Layer

```bash
SEMANTIC_LAYER_HOST=abi-semantic-layer
SEMANTIC_LAYER_PORT=10100
TRANSPORT=sse
```

### Guardian

```bash
OPA_URL=http://guardian-opa:8181
ABI_POLICY_PATH=/app/opa/policies
```

---

## Common Workflows

### Create Complete Project

```bash
# 1. Create project
abi-core create project fintech-ai \
  --domain finance \
  --with-semantic-layer \
  --with-guardian \
  --model-serving centralized

# 2. Navigate to project
cd fintech-ai

# 3. Provision models
abi-core provision-models

# 4. Add orchestration layer (Planner + Orchestrator)
abi-core add agentic-orchestration-layer

# 5. Add worker agents
abi-core add agent trader --description "Trading agent"
abi-core add agent analyst --description "Analysis agent"

# 6. Create agent cards for worker agents
abi-core add agent-card trader \
  --url "http://trader-agent:8000" \
  --tasks "execute_trade,cancel_order"

abi-core add agent-card analyst \
  --url "http://analyst-agent:8001" \
  --tasks "analyze_market,generate_report"

# 7. Start system
abi-core run --detach

# 8. Check status
abi-core status

# 9. Send query to Orchestrator
curl -X POST http://localhost:8083/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "analyze market trends and execute trade if profitable",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

### Add Agent to Existing Project

```bash
# 1. Add agent
abi-core add agent risk-manager \
  --description "Risk assessment agent"

# 2. Create agent card
abi-core add agent-card risk-manager \
  --url "http://risk-manager-agent:8002" \
  --tasks "evaluate_risk,check_compliance"

# 3. Restart services
docker-compose up -d
```

### Update Models

```bash
# Re-provision models
abi-core provision-models --force

# Restart services
docker-compose restart
```

---

## Troubleshooting

### Command not found

```bash
# Ensure package is installed
pip install abi-core-ai

# Or use full path
python -m abi_core.cli.main --help
```

### Permission denied

```bash
# Check Docker permissions
docker ps

# Add user to docker group (Linux)
sudo usermod -aG docker $USER
```

### Port conflicts

```bash
# Check used ports
docker-compose ps

# Edit .abi/runtime.yaml to change ports
# Then restart
docker-compose down
docker-compose up -d
```

---

## Next Steps

- [Complete Example](complete-example.md) - Full walkthrough
- [Agent Development](agent-development.md) - Build custom agents
- [Troubleshooting](troubleshooting.md) - Common issues

## See Also

- [Quick Start](../getting-started/quickstart.md)
- [Models Guide](models.md)
- [Policy Development](policy-development.md)
