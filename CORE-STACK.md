# 📦 ABI-Core — Framework Internals

What lives inside the `abi-core-ai` Python package and how the pieces connect.

---

## Package Structure

```
packages/
  abi-core/src/abi_core/
    agent/                — Agent framework
      agent.py            — AbiAgent base class (stream, heartbeat, tool_graph)
      agent_factory.py    — Bootstrap: A2A server + web interface + uvicorn
      abi_core_app.py     — AbiCore app runner with @agent.task/@agent.tool decorators
      llm_provider.py     — Vendor-agnostic LLM invoke (Ollama, OpenAI, etc.)
    common/               — Shared utilities
      agent_executor.py   — Request handling, deferred cleanup for ephemeral agents
      context_loader.py   — Load MCP tools, library tools, agent context
      container_runtime.py — Docker SDK wrapper for ephemeral container lifecycle
      library_tools.py    — Built-in tools: write_file, read_file, list_files, execute_command
      semantic_tools.py   — MCP tool wrappers: find_agent, register_agent, search_tool_registry
      artifact_store.py   — MinIO/S3 upload and download for artifacts
      tool_graph.py       — ToolExecutionGraph: DAG engine for @agent.task pipelines
      workflow.py          — AgentInteractionFlow: multi-agent workflow with A2A
      prompts.py          — System prompts for all agents
      utils.py            — abi_logging, clean_llm_json, truncate
      a2a_server.py       — A2A protocol server setup
      a2a_response.py     — Parse A2A responses, extract plans, find clarifications
    semantic/             — Semantic layer client
      agent_card_store.py — Weaviate CRUD for agent cards
      tool_card_store.py  — Weaviate CRUD for tool cards
      semantic_access_validator.py — OPA + Weaviate validation for MCP access
    security/             — Security utilities
      agent_auth.py       — HMAC signing, agent context for MCP calls
    opa/                  — OPA integration
      policy_loader.py    — Load and validate .rego policies
      policy_engine.py    — Evaluate OPA decisions
    tui/                  — Interactive TUI (Textual)
      app.py              — AbiConsoleApp base class
      widgets.py          — BannerWidget, ServiceTable, LogStream, ConversationPanel, CommandInput
      services.py         — DockerService, OllamaService, OrchestratorClient
    abi_mcp/              — MCP protocol utilities

  abi-agents/src/abi_agents/
    orchestrator/         — Triage + Guardian gate + Planner + workflow builder
    planner/              — Query decomposition, plan structuring, agent assignment
    builder/              — Spec parsing, tool resolution, Docker container spawning
    zombie/               — Ephemeral execution: gather → execute → synthesize → deregister

  abi-services/src/abi_services/
    Jinja2 templates for semantic layer and guardian (used by CLI scaffolding)

  abi-cli/src/abi_cli/
    cli/commands/         — create, add, remove, run, status, info, provision
    scaffolding/          — Jinja2 templates for project generation
```

---

## Key Modules Explained

### AbiCore App Runner (`abi_core_app.py`)

The entry point for every agent. Collects `@agent.task()`, `@agent.tool()`, and `@agent.mcp_tool()` decorators, builds a `ToolExecutionGraph` DAG, injects it into the agent, and starts the A2A server.

### ToolExecutionGraph (`tool_graph.py`)

Deterministic DAG execution engine. Nodes are functions with declared dependencies and input maps using `$references`. Executes in topological order with retry support. No LLM decides execution order.

### AgentInteractionFlow (`workflow.py`)

Multi-agent workflow engine built on NetworkX. The Orchestrator uses this to chain A2A calls across agents (Planner → Builder → Zombie). Supports dependency edges, parallel execution, and streaming.

### Context Loader (`context_loader.py`)

Loads an agent's runtime context: MCP tools from the semantic layer, library tools (write_file, etc.), and agent card. Also handles `self_deregister_ephemeral` for Zombie cleanup.

### Container Runtime (`container_runtime.py`)

Docker SDK wrapper used by the Builder to create ephemeral containers. Handles image selection, environment variable injection (tools, agent card, LLM config), port allocation, and container startup.

### Artifact Store (`artifact_store.py`)

MinIO/S3 client for uploading and downloading artifacts. Ephemeral agents upload their outputs here. The Orchestrator can reference artifacts in its response.

---

## How an Agent Boots

1. `main.py` creates `AbiCore()` instance
2. `@agent.task()` decorators register DAG nodes
3. `agent.run(MyAgent())` is called
4. AbiCore builds `ToolExecutionGraph` from registered nodes
5. Injects graph into `MyAgent.tool_graph`
6. `agent_factory` starts A2A server + optional web interface
7. On request: `agent.stream()` executes the DAG, yields results via SSE

---

## How an Ephemeral Agent Boots

1. Builder spawns Docker container from `abi-image`
2. Container runs `pip install abi-core-ai && abi-zombie`
3. Zombie reads config from environment variables (tools, agent card, LLM config)
4. `context_loader` loads MCP tools + library tools
5. DAG executes: `gather_context` → `analyze_and_execute` → `synthesize_and_report`
6. Artifacts uploaded to MinIO
7. `self_deregister_ephemeral` removes agent card from Weaviate
8. `os._exit(0)` kills the container
