# 🗺️ ABI Roadmap — 2026

> **Current state:** E2E pipeline functional and verified (v1.9.40+).
> User query → Orchestrator → Planner → Builder → Ephemeral → Artifacts → Cleanup. All automatic.

---

## ✅ Completed

| Area | What was built |
|------|---------------|
| Pipeline E2E | Full flow: orchestrator → planner → builder → zombie → artifacts → self-deregister |
| Orchestrator | Parallel triage + Guardian gate, semantic agent discovery, workflow construction |
| Planner | LLM-based task decomposition with steps, deps, model recommendation, agent assignment |
| Builder | Parses spec, resolves tools, generates config, spawns Docker containers, registers agent cards |
| Zombie (ephemeral) | Gather context → execute with tools → upload artifacts → self-deregister → container exit |
| Guardian | OPA policy validation, prompt injection detection, risk scoring, emergency shutdown |
| Semantic Layer | Weaviate + MCP server, agent/tool discovery via embedding similarity, HMAC auth |
| Security | OPA immutable core policies, A2A validation, semantic access validation with Weaviate fallback |
| CLI | `abi-core create swarm`, `create project`, `add agent`, `add service`, `run`, `status` |
| Monorepo | abi-core, abi-agents, abi-services, abi-cli packages with shared pyproject.toml |
| AbiCore App | `@agent.task()`, `@agent.tool()`, `@agent.mcp_tool()` decorator-based DAG registration |
| Docker Image | Base image with Ollama, agent cards, entrypoint scripts |
| TUI Console | Textual-based interactive dashboard (widgets in abi-core, scaffolded per project) |

---

## � Phase 1: Foundations (In Progress)

| Spec | Description | Depends on |
|------|-------------|------------|
| Interactive CLI / TUI | `abi-core run` launches Textual dashboard with services, logs, chat | — |
| Plan Confirmation | User approves/rejects/modifies plan before execution | CLI/TUI |
| Docker Cleanup | Auto-remove ephemeral containers (`--rm` or post-exit cleanup) | — |

---

## � Phase 2: Intelligence

| Spec | Description | Depends on |
|------|-------------|------------|
| Result Validation | Orchestrator validates task results before responding to user | — |
| Plan Learning | System learns from executions — PlanHistory in Weaviate, `search_similar_plans` | Result Validation |
| Orchestrator Synthesis Refactor | Clean up result synthesis logic | — |

---

## 📋 Phase 3: Capabilities

| Spec | Description | Depends on |
|------|-------------|------------|
| Model Management | MCP tools for Ollama: `list_installed_models`, `pull_model`, `recommend_model` | Plan Confirmation |
| Artifact Transport | Real transport of artifacts between ephemeral agents (target/tag already in plan) | — |
| Hybrid Tool Discovery | `discover_tools` + `call_tool` via semantic layer, replaces hardcoded MCP tool injection | Tools in semantic layer |

---

## 📋 Phase 4: Knowledge

| Spec | Description | Depends on |
|------|-------------|------------|
| Swarm Knowledge Base | `.abi/` directory exposed as MCP tools for agent self-knowledge | — |
| Dynamic Context Loader | Enhanced context loading with observability (partially implemented) | — |

---

## Known Issues

- Ephemeral containers remain as `Exited (0)` — `docker rm` not automatic yet
- Webapp polling fix only in template — existing projects need to regenerate
- LLM (qwen2.5:3b) occasionally misinterprets zombie prompts — may need prompt tuning or larger model

---

All specs are documented in `abi_core_framework/.abi/specs/`.
