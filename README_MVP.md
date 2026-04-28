# ABI – MVP Historical Reference

> This document describes the original MVP (2025). The project has evolved significantly since then. See [README.md](README.md) for the current state.

## What the MVP Was

The original MVP (mid-2025) demonstrated the core concepts of distributed agent-based infrastructure:

- 4 agents: Orchestrator, Planner, Actor, Guardian (+ Observer framework)
- Basic workflow orchestration with NetworkX graphs
- Weaviate semantic search for agent discovery
- OPA policy engine with core security policies
- Docker Compose deployment
- A2A protocol foundation
- MCP server with basic `find_agent` tool

## What Changed Since MVP

| Area | MVP (2025) | Current (2026) |
|------|-----------|----------------|
| Agents | Orchestrator, Planner, Actor, Guardian | Orchestrator, Planner, Builder, Guardian, Zombie (ephemeral) |
| Execution | Actor agent (long-running) | Ephemeral containers — spawn, execute, self-destruct |
| Pipeline | Basic workflow graph | Full E2E: query → plan → build → execute → artifacts → cleanup |
| Agent creation | Manual | Builder spawns Docker containers with injected tools |
| Tool discovery | Hardcoded tool lists | Semantic search in Weaviate + MCP tool registry |
| CLI | None | `abi-core create swarm`, `add agent`, `run` with TUI |
| TUI | None | Textual-based interactive dashboard |
| Agent pattern | Class-based with manual wiring | `@agent.task()` decorator-based DAG pipelines |
| Artifacts | None | MinIO storage, uploaded by ephemeral agents |
| Security | Basic OPA | Guardian gate in pipeline, HMAC for MCP, `self_deregister_ephemeral` |
| Packaging | Manual Docker setup | `pip install abi-core-ai` + monorepo (abi-core, abi-agents, abi-cli, abi-services) |

## Key Milestones After MVP

1. **Monorepo refactor** — Split into packages: abi-core, abi-agents, abi-services, abi-cli
2. **AbiCore app runner** — `@agent.task()`, `@agent.tool()`, `@agent.mcp_tool()` decorators
3. **Builder agent** — Programmatic Docker container creation for ephemeral agents
4. **Zombie agent** — Self-configuring ephemeral execution agent with self-deregister
5. **Full E2E pipeline** — Query → Orchestrator → Planner → Builder → Zombie → Artifacts → Cleanup
6. **CLI scaffolding** — `abi-core create swarm` generates complete projects
7. **TUI console** — Interactive Textual dashboard with services, logs, chat

---

For the current architecture, roadmap, and documentation, see [README.md](README.md).
