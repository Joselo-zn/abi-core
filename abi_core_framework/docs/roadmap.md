# Roadmap

## Current (v1.13.x)

What's working today:

- ✅ Decorator-based agent framework (`@agent.step`, `@agent.task`, `@agent.task_async`, `@agent.task_schedule`, `@agent.tool`, `@agent.mcp_tool`)
- ✅ Multi-provider LLM (Ollama, OpenAI, Gemini, Grok, Anthropic, Bedrock, Azure, Vertex), rebuilt on LangChain's `init_chat_model()`
- ✅ A2A protocol with HMAC authentication
- ✅ Semantic Layer (Weaviate + MCP + embedding mesh)
- ✅ Guardian + OPA security policies
- ✅ A2A access validation (strict/permissive/disabled)
- ✅ Framework-managed sessions (`abi_core.session`) — pluggable in-memory/Redis `SessionStore`, sliding-window TTL (renews on every use)
- ✅ Built-in memory API (`abi_core.memory`) — short/long-term memory for any agent, backed by the Agent Memory Server, degrades gracefully when unavailable
- ✅ Plan confirmation (approve/reject/modify a plan before execution) — built into `AbiAgent`, not swarm-specific
- ✅ Background & scheduled tasks (`@agent.task_async`, `@agent.task_schedule`)
- ✅ Rich response elements (`AgentResponse.element(...)`: image/file/pdf/audio/video/text/dataframe/qr) + custom Chainlit `.jsx` elements
- ✅ Chainlit UI: Google OAuth login, Postgres-backed persistent threads, invite-only registration *(opt-in, `OAUTH_GOOGLE_CLIENT_ID`)*
- ✅ Orchestrator + Planner + Builder reference agents *(alpha)* — no longer scaffolded by a single command (`abi-core create swarm`/`add abi-swarm` were removed; the combined system graduated into its own product, ABI Swarm); wire manually with `create project` + `add agent`/`add service` per piece
- ✅ Ephemeral agent creation (Docker containers on-demand) *(alpha)*
- ✅ Artifact Store (MinIO), with a separate public endpoint for user-facing download links
- ✅ CLI scaffolding (create project, add agent)
- ✅ Web interface (SSE streaming, Open WebUI compatible)
- ✅ Task orchestration v2 (parallel, depends_on, routing)
- ✅ MCPToolkit (dynamic MCP tool access)
- ✅ Audit logging and risk scoring

## Next (v2.x)

What's being worked on:

- 🔄 Capability matching (`abi_core.capabilities`) — task-centric model selection with measured operational envelopes; the matching/profiling logic is built and testable, but not yet wired into any agent's model selection
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
| Sessions (`abi_core.session`) | ✅ Stable |
| Built-in memory (`abi_core.memory`) | 🔶 Alpha |
| Orchestrator/Planner/Builder reference agents | 🔶 Alpha |
| Ephemeral agents | 🔶 Alpha |
| Documentation | ✅ Complete |
| Examples | ✅ Published |

---

*Last updated: September 2026*
