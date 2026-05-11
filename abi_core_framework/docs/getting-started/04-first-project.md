# Your First Project

Create a project, add an agent, run it, talk to it. 10 minutes.

## Step 1: Create the project

```bash
abi-core create project my-first-project
cd my-first-project
```

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
abi-core add agent assistant \
  --description "A helpful AI assistant" \
  --with-web-interface
```

When it asks for tasks/skills, type:

```
answer_questions
```

Now you have:

```
agents/assistant/
├── app.py              ← AbiCore instance + decorators
├── agent_assistant.py  ← Agent class
├── steps.py            ← Your step functions
├── tasks.py            ← Your task functions
├── tools.py            ← Your tools
├── prompts.py          ← Prompts (never inline)
├── config/config.py    ← LLM config, ports, env vars
├── web_interface.py    ← HTTP endpoints (SSE, REST)
├── main.py             ← Entry point
└── Dockerfile
```

## Step 3: Start it

```bash
# First time: pull the AI model (~2GB download)
docker compose up ollama -d
docker exec my-first-project-ollama ollama pull qwen2.5:3b

# Start everything
docker compose up --build -d
```

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
4. Your agent received the HTTP request, routed it to a task, called the LLM, and streamed the response back

## Next steps

Now that you have a running agent:

- 👉 [Build a proper agent with steps](../single-agent/01-first-agent.md) — understand the DAG
- 👉 [Add tools](../single-agent/03-agents-with-tools.md) — let the LLM call external APIs
- 👉 [Add memory](../single-agent/04-agents-with-memory.md) — remember conversations
