# Your First Project

Create a project, add an agent, run it, talk to it. 10 minutes.

## Step 1: Create the project

```bash
abi-core create project --name my-first-project
cd my-first-project
```

The command asks five questions. For a first project, answer `n` to the two services — you don't need them yet — and press Enter for the rest:

```
Project description (ABI-powered my-first-project project):
Domain/Industry (general):
Include semantic layer service? [y/n] (y): n
Include guardian security service? [y/n] (y): n
Choose model serving strategy [centralized/distributed] (distributed):
```

The Semantic Layer (agent discovery) and Guardian (security rules) come later in these docs; `--with-semantic-layer` and `--with-guardian` add them without asking. `distributed` vs `centralized` decides how agents share Ollama — see [Model Serving](../production/01-model-serving.md).

This creates:

```
my-first-project/
├── agents/          ← Your agents go here
├── services/        ← Support services
├── compose.yaml     ← Docker configuration
└── .abi/            ← Project metadata
```

## Step 2: Add an agent

```bash
abi-core add agent --name assistant \
  --description "A helpful AI assistant" \
  --with-web-interface
```

It asks two questions. Answer the first one and press Enter on the second:

```
Supported tasks/skills (comma-separated) (process_request,analyze_data): answer_questions
Agent URL (http://my-first-project-assistant:8001):
```

The CLI prints the ports it picked — the agent on `8001`, its web interface on `8002`.

Now you have:

```
agents/assistant/
├── app.py              ← AbiCore instance + decorators
├── agent_assistant.py  ← Agent class
├── steps.py            ← Your step functions
├── tasks.py            ← Your task functions
├── tools.py            ← Your tools
├── models.py           ← Pydantic input/output/error models
├── config/config.py    ← AI model, ports, env vars
├── web_interface.py    ← HTTP endpoints (SSE, REST)
├── main.py             ← Entry point
├── requirements.txt
├── agent_cards/        ← The agent's identity card (JSON)
└── Dockerfile
```

## Step 2b: Make it answer

The generated step is a placeholder — it returns `{"result": None}` until you fill it in. Open `agents/assistant/steps.py` and replace the body of `answer_questions_step` so it calls the model:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke


@agent.step(name="answer_questions_step", input_map={"query": "$input.query", "context_id": "$input.context_id"})
async def answer_questions_step(query, context_id=None):
    answer = await invoke(config.LLM_CONFIG, query)
    return {"answer": answer}
```

`query` is exactly the text you send in the request — no wrapping, no JSON to parse.

## Step 3: Start it

```bash
# First time: pull the AI model (~5 GB download)
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest

# Start everything
docker compose up --build -d
```

The `ollama` container name is always just `ollama` (not prefixed with your project name) — it's shared across projects and reused if one is already running.

Check it's running:

```bash
docker compose ps
```

You should see your services with status `Up`.

## Step 4: Talk to it

```bash
curl -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello! What can you do?"}'
```

You'll get a streaming response from your agent.

For a non-streaming response:

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}'
```

## Step 5: Stop it

```bash
docker compose down
```

## What just happened

1. `create project` scaffolded the infrastructure (Docker, networking, Ollama)
2. `add agent` generated the agent code with all the right patterns
3. `docker compose up` built containers and started everything
4. Your agent received the HTTP request, routed it to a task, called the AI model, and streamed the response back

## Next steps

Now that you have a running agent:

- 👉 [Build a proper agent with steps](../single-agent/01-first-agent.md) — understand the execution flow
- 👉 [Add tools](../single-agent/03-agents-with-tools.md) — let the AI call external APIs
- 👉 [Add memory](../single-agent/04-agents-with-memory.md) — remember conversations
