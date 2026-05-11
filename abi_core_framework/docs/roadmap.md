# Roadmap

## Current (v1.11.x)

What's working today:

- ✅ Decorator-based agent framework (`@agent.step`, `@agent.task`, `@agent.tool`, `@agent.mcp_tool`)
- ✅ Multi-provider LLM (Ollama, OpenAI, Gemini, Grok, Anthropic, Bedrock, Azure, Vertex)
- ✅ A2A protocol with HMAC authentication
- ✅ Semantic Layer (Weaviate + MCP + embedding mesh)
- ✅ Guardian + OPA security policies
- ✅ A2A access validation (strict/permissive/disabled)
- ✅ Orchestrator + Planner + Builder agents
- ✅ Ephemeral agent creation (Docker containers on-demand)
- ✅ Artifact Store (MinIO)
- ✅ CLI scaffolding (create project, add agent, create swarm)
- ✅ Web interface (SSE streaming, Open WebUI compatible)
- ✅ Task orchestration v2 (parallel, depends_on, routing)
- ✅ MCPToolkit (dynamic MCP tool access)
- ✅ Audit logging and risk scoring

## Next (v2.x)

What's being worked on:

- 🔄 Plan Confirmation — user approves plan before execution
- 🔄 Context Engine (Redis) — shared context across agents
- 🔄 TUI improvements — interactive terminal dashboard
- 🔄 Result validation — verify agent outputs against schemas
- 🔄 Swarm knowledge base — persistent learning across sessions

## Future

Ideas and directions:

- Parallel task execution (declarative `parallel=["a", "b"]` in tasks)
- Workflow persistence and resume
- Multi-node deployment (Kubernetes-native)
- Self-optimizing workflows (agents learn from execution history)
- Plugin ecosystem for community tools
- Visual workflow editor

## Status

| Component | Status |
|-----------|--------|
| Core framework | ✅ Stable |
| CLI | ✅ Stable |
| A2A + Security | ✅ Stable |
| Semantic Layer | ✅ Stable |
| Orchestration | ✅ Stable |
| Documentation | ✅ Complete |
| Examples | ✅ Published |

---

*Last updated: May 2026*
