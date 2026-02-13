# Your First Project

In this guide, you'll create your first project with ABI-Core step by step. By the end, you'll have a working agent you can query.

## What You'll Build

A simple project with:
- ✅ An AI agent
- ✅ Language model (qwen2.5:3b)
- ✅ Interface for queries

**Estimated time**: 10 minutes

## Step 1: Create the Project

Open your terminal and run:

```bash
abi-core create project my-first-project
```

**What does this command do?**
- Creates directory structure
- Configures Docker
- Prepares environment

**Expected output**:
```
🚀 Creating ABI project: my-first-project
✅ Project structure created
✅ Docker configuration created
✅ Runtime configuration created

📁 Project created at: ./my-first-project

Next steps:
  cd my-first-project
  abi-core provision-models
```

## Step 2: Navigate to Project

```bash
cd my-first-project
```

**Created structure**:
```
my-first-project/
├── agents/              # Your agents will go here
├── services/            # Support services
├── compose.yaml         # Docker configuration
├── .abi/
│   └── runtime.yaml     # Project configuration
└── README.md
```

## Step 3: Provision Models

This step downloads the AI model your agent will use:

```bash
abi-core provision-models
```

**What does this command do?**
1. Starts Ollama service
2. Downloads `qwen2.5:3b` (~2GB)
3. Downloads embedding model
4. Updates configuration

**Expected output**:
```
🚀 Starting model provisioning...
📦 Model serving mode: centralized
🔄 Starting Ollama service...
✅ Ollama service started

📥 Downloading qwen2.5:3b...
████████████████████████████ 100%
✅ qwen2.5:3b downloaded successfully

📥 Downloading nomic-embed-text:v1.5...
████████████████████████████ 100%
✅ nomic-embed-text:v1.5 downloaded successfully

✅ Models provisioned successfully
```

**Note**: First time takes several minutes depending on your connection.

## Step 4: Create Your First Agent

Now create an agent:

```bash
abi-core add agent assistant --description "My first AI agent"
```

**What does this command do?**
- Creates agent code
- Configures Dockerfile
- Registers agent in project

**Expected output**:
```
✅ Agent 'assistant' added successfully!
📁 Location: agents/assistant
🚀 Port: 8000
📦 Docker service added to compose file
```

**Files created**:
```
agents/assistant/
├── __init__.py
├── agent_assistant.py    # Agent code
├── main.py               # Entry point
├── models.py             # Data models
├── Dockerfile            # Docker configuration
└── requirements.txt      # Dependencies
```

## Step 5: Start the System

Start all services:

```bash
abi-core run
```

Or with Docker Compose directly:

```bash
docker-compose up -d
```

**What starts?**
- Ollama service (AI models)
- Your assistant agent

**Verify it's running**:
```bash
docker-compose ps
```

You should see:
```
NAME                          STATUS    PORTS
my-first-project-ollama       Up        0.0.0.0:11434->11434/tcp
assistant-agent               Up        0.0.0.0:8000->8000/tcp
```

## Step 6: Test Your Agent

### Option 1: With curl

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, how are you?",
    "context_id": "test-001",
    "task_id": "task-001"
  }'
```

**Expected response**:
```json
{
  "content": "Hello! I'm doing well, thank you for asking. I'm your AI assistant. How can I help you today?",
  "response_type": "text",
  "is_task_completed": true
}
```

### Option 2: With Python

Create a file `test_agent.py`:

```python
import requests

response = requests.post(
    "http://localhost:8000/stream",
    json={
        "query": "What is artificial intelligence?",
        "context_id": "test-001",
        "task_id": "task-001"
    }
)

print(response.json())
```

Run:
```bash
python test_agent.py
```

### Option 3: Browser

Open your browser and go to:
```
http://localhost:8000/docs
```

You'll see the Swagger interface where you can test the agent interactively.

## Step 7: View Logs

To see what your agent is doing:

```bash
# View logs of all services
docker-compose logs -f

# View only agent logs
docker-compose logs -f assistant-agent

# View only Ollama logs
docker-compose logs -f my-first-project-ollama
```

## Step 8: Stop the System

When you're done:

```bash
# Stop services
docker-compose down

# Stop and remove volumes (models)
docker-compose down -v
```

## Next Steps

Congratulations! You have your first project running. Now you can:

1. [Create a more complex chatbot](../single-agent/02-simple-chatbot.md)
2. [Add tools to your agent](../single-agent/03-agents-with-tools.md)
3. [Add conversational memory](../single-agent/04-agents-with-memory.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
