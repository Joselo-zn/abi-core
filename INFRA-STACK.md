# 🛠 ABI Infrastructure

How ABI projects are deployed and operated today.

---

## Current Infrastructure (Docker Compose)

ABI runs entirely on Docker Compose. One command starts everything:

```bash
abi-core create swarm --name "my-swarm"
cd my-swarm
abi-core run
```

### What Gets Deployed

| Service | Image / Build | Port | Role |
|---------|--------------|------|------|
| Orchestrator | Built from `agents/orchestrator/` | 8000 | Query coordination, Guardian gate, workflow construction |
| Planner | Built from `agents/planner/` | 8001 | Task decomposition, agent assignment |
| Builder | Built from `agents/builder/` | 8002 | Ephemeral container creation via Docker SDK |
| Guardian | Built from `services/guardian/` | 11438 | OPA policy validation, security gate |
| Semantic Layer | Built from `services/semantic_layer/` | 10100 | MCP server, agent/tool discovery |
| Weaviate | `semitechnologies/weaviate:1.32.4` | 8080 | Vector database for embeddings |
| Ollama | `ollama/ollama` | 11434 | Local LLM inference |
| MinIO | `minio/minio` | 9000 | S3-compatible artifact storage |
| OPA | `openpolicyagent/opa` | 8181 | Policy engine |
| Web App | Built from `services/web_api/` | 8000 | FastAPI REST API + webapp |

### Ephemeral Containers

The Builder spawns additional Docker containers at runtime for each task:
- Based on `smarbuy/abi-image:latest` (the ABI base image)
- Each installs `abi-core-ai` via pip on boot
- Tools, agent card, and config injected as environment variables
- Container self-destructs after task completion

### Networking

All services run on a shared Docker Compose network. Service names are DNS-resolvable:
- `http://my-swarm-orchestrator:8000`
- `http://my-swarm-semantic-layer:10100`
- `http://my-swarm-ollama:11434`

---

## Security Infrastructure

| Component | What it does |
|-----------|-------------|
| OPA | Policy engine with `.rego` files. Immutable core policies auto-generated at startup. |
| Guardian | Agent that calls OPA for every request. Prompt injection detection, risk scoring. |
| HMAC | MCP tool calls between agents are signed with HMAC from agent cards. |
| Agent Cards | JSON identity documents registered in Weaviate. Carry capabilities, skills, URL. |
| Audit Logs | Every OPA decision, A2A interaction, and MCP call is logged. |

---

## ABI Base Image (`abi-image/`)

The Docker base image used by all agents and ephemeral containers:

```
abi-image/
  Dockerfile              — Base image build
  abi-ollama/             — Ollama installation scripts
  agent_cards/            — Default agent card JSONs
  agents.d/               — Entrypoint and model loader scripts
  shared/                 — MOTD and shared utilities
  requirements.txt        — Base Python dependencies
```

Ephemeral agents don't rebuild this image. They use it as-is and install `abi-core-ai` at boot via pip, getting the latest version automatically.

---

## Project Structure (Generated)

```
my-swarm/
  agents/
    orchestrator/         — Orchestrator agent + config + Dockerfile
    planner/              — Planner agent + config + Dockerfile
    builder/              — Builder agent + config + Dockerfile
  services/
    web_api/              — FastAPI webapp
    semantic_layer/       — MCP server + Weaviate integration
    guardian/             — Guardian agent + OPA policies
      opa/policies/       — .rego policy files
  compose.yaml            — Docker Compose orchestration
  console.py              — TUI dashboard (customizable)
  .abi/
    runtime.yaml          — Project configuration
```

---

## Future Infrastructure (Not Yet Implemented)

These are potential additions for production deployments:

- **Kubernetes / Helm** — For multi-node clusters and horizontal scaling
- **Terraform** — For cloud provisioning (currently everything is local)
- **Prometheus + Grafana** — For metrics and monitoring
- **OpenTelemetry** — For distributed tracing across agents
- **Vault** — For secrets management (currently env vars)

The current Docker Compose setup handles single-machine deployments. Kubernetes support is on the roadmap for production-scale deployments.
