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
abi-core create project --name my-app \
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
abi-core add agent --name analyst \
  --description "Analyzes financial data" \
  --model qwen3:latest \
  --with-web-interface
```

Creates: `agents/<name>/` with app.py, agent_<name>.py, steps.py, tasks.py, tools.py, models.py, config/, main.py, requirements.txt, Dockerfile, agent_cards/ (plus web_interface.py with `--with-web-interface`).

### `abi-core add service`

```bash
abi-core add service <type> [--name <name>] [--domain <domain>]
```

| Type | Description |
|------|-------------|
| `semantic-layer` | AI agent discovery and routing service (fixed name `semantic_layer`). Shortcut: `abi-core add semantic-layer`. |
| `mcp-api` | FastMCP/API central connection point service |
| `agent-memory` | Short/long-term memory — provisions Redis 8 + Agent Memory Server (AMS) and wires `AGENT_MEMORY_URL` into existing (and future) agents. Works for any agent, not just a swarm. See [Environment Variables → Agent Memory](environment-variables.md#agent-memory-redis-ams). |

### `abi-core add agent-card`

```bash
abi-core add agent-card --name <name> [--description "..."] [--model qwen3:latest] [--url http://<host>:<port>] [--tasks task_a,task_b]
```

Creates only the agent card — the JSON identity other agents discover in the Semantic Layer — for an agent that already exists or runs outside this project. `abi-core add agent` already creates one for its agent; use this to register something else, or to regenerate a card after `abi-core remove agent-card`.

### `abi-core add policies`

```bash
abi-core add policies --name <name> [--domain <domain>]
```

Creates a starter Rego file, `policies/<name>.rego` at the project root, with package `<name>.custom`, and records it in `.abi/runtime.yaml`.

```{warning}
As generated, this file is never applied. OPA only loads `services/guardian/opa/policies/`, and Guardian only reads the `abi.custom` package. To use it, change its first line to `package abi.custom`, move it to `services/guardian/opa/policies/`, and restart OPA — or write the file there yourself, as shown in [Policy Development](../security/03-policy-development.md).
```

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
| `--build` | Rebuild images first (`docker compose up --build`) |
| `--logs` | Stay in the foreground and stream every container's output. `Ctrl+C` stops the stack (`docker compose down`) |
| `-d`, `--detach` | Start in the background without the closing summary (background is already the default without `--logs`) |

Without `--logs`, it runs `docker compose up -d` and prints the project's services and ports.

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
| `abi-core provision-models [--force]` | Pull the project's LLM and embedding models into Ollama (per agent in `distributed` mode). `--force` downloads them again |
| `abi-core status` | Show running services and ports |
| `abi-core info` | Show project configuration |
| `abi-core remove agent <name> [--force] [--dry-run] [--keep-compose] [--keep-runtime]` | Remove an agent. `--dry-run` shows what would go; `--keep-compose`/`--keep-runtime` leave those files untouched |
| `abi-core remove service <name> [--force] [--dry-run]` | Remove a service |
| `abi-core remove agent-card <name> [--force]` | Remove only an agent's card from the Semantic Layer (e.g. to regenerate it), leaving the agent itself in place |

---

## Typical workflow

```bash
abi-core create project --name my-app --with-semantic-layer
cd my-app
abi-core add agent --name my-agent --description "..." --with-web-interface
docker compose up ollama -d
abi-core provision-models
docker compose up --build -d
```
