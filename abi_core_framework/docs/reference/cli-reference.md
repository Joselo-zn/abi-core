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
| `--model` | LLM model (default: `qwen3:latest`) |
| `--with-web-interface` | Add HTTP/SSE endpoints |

```bash
abi-core add agent analyst \
  --description "Analyzes financial data" \
  --model qwen3:latest \
  --with-web-interface
```

Creates: `agents/<name>/` with app.py, steps.py, tasks.py, tools.py, prompts.py, config/, Dockerfile, agent_cards/.

### `abi-core add service`

```bash
abi-core add service <type> [--name <name>] [--domain <domain>]
```

| Type | Description |
|------|-------------|
| `semantic-layer` | AI agent discovery and routing service (fixed name `semantic_layer`). Shortcut: `abi-core add semantic-layer`. |
| `guardian` | Security policy enforcement service (placeholder) |
| `guardian-native` | Native Guardian service based on abi-core guardial |
| `mcp-api` | FastMCP/API central connection point service |
| `agent-memory` | Short/long-term memory — provisions Redis 8 + Agent Memory Server (AMS) and wires `AGENT_MEMORY_URL` into existing (and future) agents. Works for any agent, not just a swarm. See [Environment Variables → Agent Memory](environment-variables.md#agent-memory-redis-ams). |

### `abi-core add chainlit`

```bash
abi-core add chainlit [--url http://<project>-<agent>:<port>] [--title "My Chat"] [--dir ui]
```

Adds a [Chainlit](https://docs.chainlit.io) chat UI **as a Docker service**, wired into
the project's `compose.yaml` and network. It's a thin SSE client over an agent's
`/stream` endpoint that opens a framework-managed session (so multi-turn stays coherent)
and streams status/result updates.

If `--url` is omitted, the target agent is **auto-detected** from `.abi/runtime.yaml`
(the agent with a web interface, preferring the orchestrator). The UI gets a dynamic
host port; started by `abi-core run` alongside the rest of the stack.

| Option | Description |
|--------|-------------|
| `--url` | Target agent `/stream` URL as a Docker **service name** (auto-detected if omitted) |
| `--title` | UI title (default `<project> Chat`) |
| `--dir` | Output directory (default `ui`) |

```bash
abi-core add chainlit     # auto-detects the web agent, adds the service
abi-core run              # builds + starts everything, including the UI
```

The command prints the host URL (e.g. `http://localhost:8500`). Override the target at
runtime with the `ABI_AGENT_URL` environment variable on the `chatui` service.

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

## Capabilities

### `abi-core capabilities`

```{note}
**Alpha.** Task-centric model capability matching — profiles are not yet wired
into agent model selection.
```

```bash
abi-core capabilities list [--source profiles.json]
abi-core capabilities show <model> [--source profiles.json] [--radar out.png]
abi-core capabilities profile <model> [--host http://localhost:11434] [--output profile.json] [--reps 10] [--timeout 300]
```

`list`/`show` read model profiles (default: the built-in seed catalog); `profile`
measures a real Ollama model's operational envelope (structured output, reasoning,
instruction following, code generation) via leveled probes and writes a JSON profile.

---

## UI

### `abi-core ui chainlit`

```bash
abi-core ui chainlit --url http://localhost:8083 [--title "ABI"] [--port 8000] [--headless]
```

Runs a standalone Chainlit chat UI process against an agent's `/stream` URL —
distinct from `abi-core add chainlit`, which instead wires Chainlit in as a
permanent Docker service in `compose.yaml`.

---

## Other commands

| Command | Description |
|---------|-------------|
| `abi-core provision-models` | Pull LLM + embedding models into Ollama |
| `abi-core status` | Show running services and ports |
| `abi-core info` | Show project configuration |
| `abi-core remove agent <name>` | Remove an agent |
| `abi-core remove service <name>` | Remove a service |
| `abi-core remove agent-card <name>` | Remove only an agent's card from the semantic layer (e.g. to regenerate it), leaving the agent itself in place |

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
