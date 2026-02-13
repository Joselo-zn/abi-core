# ABI Core CLI - Modular Structure

## 📁 Structure

```
cli/
├── main.py              # CLI principal con configuración base
├── banner.py            # Banner ASCII de ABI
├── commands/            # Comandos modulares
│   ├── __init__.py     # Exports de comandos
│   ├── utils.py        # Utilidades compartidas
│   ├── create.py       # Comandos 'create'
│   ├── add.py          # Comandos 'add'
│   ├── run.py          # Comando 'run'
│   ├── status.py       # Comando 'status'
│   └── info.py         # Comando 'info'
└── README.md           # Esta documentación
```

## 🔧 Modular Architecture

### **main.py**
- Base CLI configuration with Click
- Modular command registration
- Custom banner with Rich
- Main entry point

### **commands/utils.py**
- Shared functions between commands
- Code generation templates
- Configuration utilities
- Shared Rich console

### **Modular Commands**

#### **create.py**
- `create project` - Create new ABI projects
- Complete project scaffolding
- Optional service generation

#### **add.py**
- `add agent` - Add agents to project
- `add service` - Add services (semantic-layer, guardian)
- `add policies` - Add security policies

#### **run.py**
- `run` - Execute project with Docker Compose
- Support for different modes (dev, prod, test)
- System information and status

#### **status.py**
- `status` - Project and services status
- Information about agents, services and policies
- Docker container status

#### **info.py**
- `info` - Detailed project information
- Configuration and structure
- Next steps suggestions

## 🚀 Modularization Benefits

### **Maintainability**
- Each command in its own file
- Clearly separated responsibilities
- Easy functionality location

### **Scalability**
- Adding new commands is simple
- Reuse of common utilities
- Consistent structure

### **Testability**
- Each module can be tested independently
- Specific imports for testing
- More granular mocking

### **Collaboration**
- Multiple developers can work in parallel
- Fewer merge conflicts
- More readable code

## 📝 Adding New Commands

### 1. Create new command file
```python
# commands/nuevo_comando.py
import click
from .utils import console

@click.command()
def new_command():
    """Description of the new command"""
    console.print("New command working!")
```

### 2. Register in __init__.py
```python
# commands/__init__.py
from .new_command import new_command

__all__ = ['create', 'add', 'run', 'status', 'info', 'new_command']
```

### 3. Register in main.py
```python
# main.py
from .commands import new_command

cli.add_command(new_command)
```

## 🧪 Testing

```bash
# Test imports
python3 test_modular_cli.py

# Test specific commands
python3 -c "import sys; sys.path.append('src'); from abi_core.cli.main import cli; cli(['--help'])"
```

## 🔄 Migration Completed

✅ **Before**: Everything in `main.py` (1118+ lines)
✅ **After**: Modular and organized
- `main.py`: 37 lines (configuration only)
- `commands/`: 5 specialized files
- `utils.py`: Shared functions

## 📋 Available Commands

| Command | File | Description |
|---------|------|-------------|
| `create project` | `create.py` | Create new ABI project |
| `add agent` | `add.py` | Add agent |
| `add service` | `add.py` | Add service |
| `add policies` | `add.py` | Add policies |
| `run` | `run.py` | Execute project |
| `status` | `status.py` | Project status |
| `info` | `info.py` | Project information |

## 🆕 **New Features: Agent Cards**

### **Agent Cards Management**

#### **Automatic Agent Card Creation**
When adding a semantic-layer service, it automatically creates:
- Directory `services/{service_name}/mcp_server/agent_cards/`
- Example agent card with project configuration

#### **Command: `add agent-card`**
Creates agent cards for semantic layer registration.

**Syntax:**
```bash
abi-core add agent-card --name "AgentName" [OPTIONS]
```

**Options:**
- `--name, -n` *(required)* - Agent name
- `--description, -d` - Agent description
- `--model` - LLM model (default: qwen2.5:3b)
- `--url` - Agent URL (default: http://localhost:8000)
- `--tasks` - Supported tasks separated by commas

**Example:**
```bash
abi-core add agent-card \
  --name "DataAnalyzer" \
  --description "Agent specialized in data analysis" \
  --model "llama3.2:3b" \
  --url "http://localhost:8001" \
  --tasks "analyze_data,generate_report,process_metrics"
```

#### **Generated Agent Card Structure**
```json
{
  "@context": ["https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"],
  "@type": "Agent",
  "id": "agent://dataanalyzer",
  "name": "DataAnalyzer",
  "description": "Agent specialized in data analysis",
  "url": "http://localhost:8001",
  "version": "1.0.0",
  "capabilities": {
    "streaming": "True",
    "pushNotifications": "True",
    "stateTransitionHistory": "False"
  },
  "supportedTasks": ["analyze_data", "generate_report", "process_metrics"],
  "llmConfig": {
    "provider": "ollama",
    "model": "llama3.2:3b",
    "temperature": 0.1
  },
  "skills": [
    {
      "id": "analyze_data",
      "name": "Analyze Data",
      "description": "Analyze Data functionality for DataAnalyzer",
      "tags": ["analyze_data", "processing", "analysis"],
      "examples": ["Execute analyze_data operation"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ]
}
```

### **Enhanced Semantic Layer**

The semantic layer now includes:

#### **Agent Management APIs**
- `GET /v1/agents` - List registered agents
- `POST /v1/register_agent` - Register new agent
- `DELETE /v1/agents/{agent_id}` - Unregister agent
- `POST /v1/tools/find_agent` - Find agent by query
- `POST /v1/tools/get_agent` - Get specific agent

#### **Security Features**
- **Availability Verification**: Only agents with agent cards can access
- **Authorization**: Only authorized agents in agent_cards directory
- **Dynamic Management**: Real-time registration/unregistration

### **Workflow with Agent Cards**

1. **Create Project with Semantic Layer**
   ```bash
   abi-core create project --name "MyProject" --with-semantic-layer
   ```

2. **Register Agents**
   ```bash
   abi-core add agent-card --name "MyAgent" --url "http://localhost:8001"
   ```

3. **The Semantic Layer Automatically**
   - Loads agent cards on startup
   - Provides semantic search
   - Validates agent availability
   - Manages dynamic registration

### **Benefits**

✅ **Access Control**: Only authorized agents  
✅ **Availability Verification**: Automatic detection of offline agents  
✅ **Semantic Search**: Finds the best agent for each task  
✅ **Centralized Management**: Single registration point  
✅ **Security**: Agent validation before access  

Modularization is complete and working correctly! 🎉