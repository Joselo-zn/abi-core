# CLI Reference

## Create

### `abi-core create project`

```bash
abi-core create project --name <name> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name, -n` | Project name (required) |
| `--description, -d` | Project description |
| `--domain` | Domain (finance, healthcare, general) |
| `--with-semantic-layer` | Include Weaviate + MCP server |
| `--with-guardian` | Include Guardian + OPA |
| `--model-serving` | `centralized` or `distributed` |

```bash
abi-core create project my-app \
  --with-semantic-layer \
  --with-guardian \
  --model-serving centralized
```

### `abi-core create swarm`

Creates a full project + Orchestrator + Planner + Builder in one command.

```bash
abi-core create swarm --name my-swarm
```

---

## Add

### `abi-core add agent`

```bash
abi-core add agent --name <name> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name, -n` | Agent name (required) |
| `--description, -d` | What the agent does |
| `--model` | LLM model (default: `qwen2.5:3b`) |
| `--with-web-interface` | Add HTTP/SSE endpoints |

```bash
abi-core add agent analyst \
  --description "Analyzes financial data" \
  --model qwen2.5:3b \
  --with-web-interface
```

Creates: `agents/<name>/` with app.py, steps.py, tasks.py, tools.py, prompts.py, config/, Dockerfile, agent_cards/.

### `abi-core add service`

```bash
abi-core add service <type>
```

Types: `semantic-layer`, `guardian-native`

---

## Run

### `abi-core run`

```bash
abi-core run [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--logs` | Show container output |
| `--build` | Rebuild containers first |

Equivalent to `docker compose up -d`.

---

## Other commands

| Command | Description |
|---------|-------------|
| `abi-core provision-models` | Pull LLM + embedding models into Ollama |
| `abi-core status` | Show running services and ports |
| `abi-core info` | Show project configuration |
| `abi-core remove agent <name>` | Remove an agent |
| `abi-core remove service <name>` | Remove a service |

---

## Typical workflow

```bash
abi-core create project my-app --with-semantic-layer
cd my-app
abi-core add agent my-agent --description "..." --with-web-interface
docker compose up ollama -d
abi-core provision-models
docker compose up --build -d
```
