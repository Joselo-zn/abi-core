# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Agent Memory Server (AMS) in swarm scaffolding** — `abi-core create swarm` and the
  CLI generator (`add.py`) now provision two extra services for system-wide memory:
  - `<project>-redis-stack` — Redis 8 (bundles RediSearch/RedisJSON; required for the
    `HSETEX` command used by AMS) with `--appendonly yes` persistence.
  - `<project>-agent-memory` — `redislabs/agent-memory-server` exposing working
    (short-term) and long-term memory on port 8000.
  - The Builder injects `AGENT_MEMORY_URL=http://<project>-agent-memory:8000` into
    ephemeral agents so they can recall/store context.
  - AMS runs fully local via Ollama (LiteLLM): `GENERATION_MODEL`/`FAST_MODEL`/`SLOW_MODEL`
    = `ollama/qwen2.5:3b`, `EMBEDDING_MODEL` = `ollama/nomic-embed-text:v1.5` (768 dims).

### Fixed
- `AgentResponse.input_required(prompt, **kwargs)` — now accepts optional metadata
  (e.g. `status`, `questions`) preserved under `meta`. Previously raised
  `TypeError: unexpected keyword argument 'status'` when an agent emitted a
  clarification request, which broke the Planner → Orchestrator clarification flow.
- `A2AResponse.is_input_required` / `is_completed` / `is_failed` — now recognize
  protobuf `TaskState` values in all forms: integer (`"6"`), enum name
  (`TASK_STATE_INPUT_REQUIRED`), and legacy string (`input-required`). Previously
  only matched the legacy string, so clarification requests over a2a-sdk 1.0
  (protobuf, integer states) were never detected by the Orchestrator.

### Breaking Changes
- **a2a-sdk upgraded to 1.0+** — `AgentCard` is now protobuf (was pydantic). If you have a custom `config.py` that does `AgentCard(**data)`, replace it with:
  ```python
  from abi_core.common.agent_card_loader import load_agent_card
  card, meta = load_agent_card("path/to/card.json")
  ```
  The `meta` dict contains ABI-specific fields (`auth`, `id`, `supportedTasks`, `llmConfig`).
  Access URL via `card.supported_interfaces[0].url` or `get_agent_url(card)`.
- **Docker image stays on a2a-sdk 0.3.25** — existing projects running on the base image are unaffected. Only projects that install `abi-core-ai` directly from PyPI get the new SDK.

### Added
- `abi_core.common.agent_card_loader` — new module that separates A2A protocol fields from ABI metadata when loading agent cards
- `load_agent_card(path)` → returns `(AgentCard, abi_metadata_dict)`
- `build_agent_card(dict)` → same but from a dict instead of file
- `get_agent_url(card)` → extracts URL from `supported_interfaces[0]`

### Changed
- `a2a_server.py` — uses `create_jsonrpc_routes` + `create_agent_card_routes` (replaces removed `A2AStarletteApplication`)
- `agent_executor.py` — rewritten for protobuf types (`Part`, `TaskState.TASK_STATE_WORKING`)
- `abi_a2a.py` — uses `ClientFactory.connect()` and `Client.send_message()` (replaces `A2AClient`)
- `workflow.py` — updated event handling for new client response format
- `semantic_tools.py` — `tool_find_agent`/`tool_list_agents` use `build_agent_card()`
- All agent `config.py` files — use `load_agent_card()` instead of `AgentCard(**data)`
- CLI scaffolding templates updated for new pattern

### Added
- **AbiCore Application Runner**: FastAPI-style `agent = AbiCore()` with auto-config import
  - Auto-imports `config` and `AGENT_CARD` from the local `config` package
  - `agent.run(MyAgent())` starts the A2A server with zero boilerplate
  - Supports `web_interface_cls` and `interface_name` for web interfaces
- **Decorator-Based Task/Tool Registration**:
  - `@agent.step(name, depends_on, input_map)` — deterministic DAG step
  - `@agent.tool(name, depends_on, input_map)` — DAG step + LangChain tool for LLM
  - `@agent.mcp_tool(name, input_map)` — remote MCP tool via MCPToolkit with HMAC auth
  - `input_map` supports `$references` (e.g. `$clean_data.result`, `$input.query`)
  - Tasks/tools are wired into `ToolExecutionGraph` DAG automatically on `agent.run()`
- **AbiAgent Base Class Enhancements**:
  - Default `stream()` with SSE heartbeat (15s keepalive for CloudFront)
  - `self.tool_graph` — injected by AbiCore when decorators are used
  - `self.extra_tools` — LangChain tools from `@agent.tool()` decorators
  - `AgentResponse` typed responses: `.success()`, `.error()`, `.status()`, `.empty()`, `.input_required()`
- **LLM Provider**: `create_llm(llm_config)` supporting Ollama, OpenAI, Anthropic, Bedrock, Azure, Vertex AI, Grok
- **Agent Factory**: `agent_factory()` encapsulates all startup boilerplate (logging, web interface, A2A server)
- **Dual Transport Support for MCP Client**: Added support for both SSE and Streamable HTTP transports
  - `abi_core.abi_mcp.client.init_session()` now supports `transport='sse'` or `transport='streamable-http'`
  - SSE transport uses `/sse` endpoint (default, unidirectional streaming)
  - Streamable HTTP transport uses `/mcp` endpoint (bidirectional streaming)
  - Environment variable `MCP_TRANSPORT` for dynamic transport selection
  - Backward compatible - SSE remains the default transport
- **Transport Documentation**: Added comprehensive guide at `docs/user-guide/mcp-transports.md`
- **Transport Examples**: Added `examples/mcp_transport_examples.py` demonstrating both transports
- **Transport Tests**: Added unit tests for both transport protocols
- **Session Management Guide**: Added `docs/SESSION_MANAGEMENT.md` with best practices
  - Solutions for "Session terminated" errors
  - Proper session lifecycle management
  - Retry logic patterns
  - Connection pooling examples
  - Debugging and monitoring techniques
- **ToolExecutionGraph**: Deterministic tool execution graph built on LangGraph
  - DAG-based execution with topological ordering
  - `$-reference` resolution between nodes (e.g. `$input.user_query`, `$step1.result`)
  - Retry with exponential backoff per node
  - Checkpoint/resume on failures
  - Construction from JSON config or programmatic API
  - Dual execution mode: MCP tools (`tool` param) and local functions (`fn` param, sync or async)
  - `register_fn("name", callable)` for JSON-defined graphs with local functions
- **Automatic Agent Card Creation**: `abi-core add agent` now includes interactive skills session
  - Prompts for supported tasks/skills during agent creation
  - Generates signed agent card automatically
  - Saves card to agent directory and semantic layer (if exists)
  - Registers card in `runtime.yaml` and updates docker-compose
  - No need to run `add agent-card` separately

### Changed
- **MCP Client**: Enhanced `init_session()` to automatically select correct endpoint based on transport
- **Default MCP Transport**: Changed from `sse` to `streamable-http` across all components
  - Env var `MCP_TRANSPORT=sse` still works for override
- **Logging**: Migrated all `logger.*` calls to `abi_logging()` across the framework
- **Workflow Classes**: Renamed for clarity
  - `WorkflowGraph` → `AgentInteractionFlow` (backward-compatible aliases maintained)
  - `WorkflowNode` → `InteractionFlowNode`
  - `WorkflowState` → `InteractionFlowState`
- **ServerConfig**: Updated documentation to clarify supported transports ('sse' and 'streamable-http')
- **Utils**: Updated `get_mcp_server_config()` to support both transports via environment variables
- **Session Cleanup**: Improved resource cleanup in Streamable HTTP transport
  - Added explicit cleanup in finally blocks
  - Better logging for debugging session lifecycle
  - Prevents "Session terminated" errors from unclosed streams
- **MCPToolkit**: Enhanced error handling and added retry logic
  - Improved error handling with session-level error catching
  - Added `call_with_retry()` method for automatic retry on transient errors
  - Exponential backoff for retry attempts
  - Automatic detection of retryable errors (session terminated, connection issues)

### Fixed
- **Transport Validation**: Added proper validation for unsupported transport types
- **Streamable HTTP API**: Corrected implementation based on official MCP SDK documentation
  - `streamable_http_client` returns **3 elements**: `(read_stream, write_stream, connection_metadata)`
  - `sse_client` returns **2 elements**: `(read_stream, write_stream)`
  - Updated `init_session()` to properly unpack 3 elements for Streamable HTTP
  - Third element (connection metadata) is ignored with `_` placeholder
  - Reference: [MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk)
- **FastMCP API Update**: Updated all MCP server templates to use new FastMCP API
  - `FastMCP()` constructor no longer accepts `host` and `port` parameters
  - Host and port now passed to `mcp.run(transport=transport, host=host, port=port)`
  - Updated templates: `service_semantic_layer/layer/mcp_server/server.py.j2`
  - Updated scaffolding: `abi-cli/scaffolding/service_semantic_layer/layer/mcp_server/server.py.j2`
  - Updated testproject: `testproject/services/semantic_layer/layer/mcp_server/server.py`

## [1.5.8] - 2024-12-20

### Fixed
- **Version Synchronization**: Updated all version references to 1.5.8 for next PyPI release
- **Package Dependencies**: All requirements.txt files now correctly reference `abi-core-ai>=1.12.0`
- **Documentation**: Updated version references across all documentation files to 1.5.8

## [1.5.7] - 2024-12-20

### Fixed
- **Version Synchronization**: Updated all version references to match PyPI published version 1.5.7
- **Package Dependencies**: All requirements.txt files now correctly reference `abi-core-ai>=1.5.7`
- **Documentation**: Updated version references across all documentation files to 1.5.7

## [1.5.6] - 2024-12-20

### Added
- **AbiAgent Base Class**: Restored missing `abi_core.agent.agent.AbiAgent` base class
  - Fixed `ModuleNotFoundError: No module named 'abi_core.agent'` errors
  - Added proper abstract base class with `stream()` method
  - Includes lazy imports in `abi_core.__init__.py`
- **Semantic Module Exports**: Enhanced `abi_core.semantic` module exports
  - Added `validate_semantic_access` function export
  - Improved module structure for better accessibility

### Fixed
- **Import Dependencies**: Resolved missing module imports after monorepo migration
- **Template Consistency**: Updated all requirements.txt templates to use version 1.5.8
- **Documentation Version**: Updated Sphinx configuration to reflect current version

### Changed
- **Version Alignment**: All package requirements now point to `abi-core-ai>=1.12.0`
- **Documentation**: Updated version references across all documentation files

## [1.4.0] - 2024-12-16

### Added
- **Monorepo Modular Architecture**: Complete migration to modular package structure
  - `packages/abi-core/` - Core libraries (common/, security/, opa/, abi_mcp/)
  - `packages/abi-agents/` - Agent implementations (orchestrator/, planner/)
  - `packages/abi-services/` - Services (semantic-layer/, guardian/)
  - `packages/abi-cli/` - CLI and scaffolding tools
  - `packages/abi-framework/` - Umbrella package with unified API
  - Maintains full backward compatibility with existing imports
  - Symlinks ensure seamless transition during development
- **Enhanced Open WebUI Compatibility**: Improved web interface for agents
  - Fixed `Unclosed client session` errors in streaming responses
  - Corrected media types from `application/x-ndjson` to `text/plain`
  - Added proper `Connection: close` headers for Open WebUI
  - Fixed newline escaping in streaming responses (`\\n` → `\n`)
  - Enhanced CORS headers for better browser compatibility

### Changed
- **Project Structure**: Reorganized codebase into modular packages for better maintainability
- **Web Interface Templates**: Updated all agent web interfaces for Open WebUI compatibility
- **Import Paths**: Maintained backward compatibility while enabling new modular imports
- **Documentation**: Updated to reflect v1.5.2 architecture and features

### Fixed
- **Web Interface Streaming**: Resolved connection leaks in Open WebUI integration
- **Template Synchronization**: Ensured consistency between orchestrator and agent templates
- **URL Parsing**: Fixed malformed URLs in service communication
- **Connection Management**: Improved HTTP connection cleanup in streaming responses

### Technical Improvements
- **Modular Development**: Each package can be developed and tested independently
- **Community Collaboration**: Easier contribution workflow with focused packages
- **Deployment Flexibility**: Granular control over which components to deploy
- **Maintenance**: Simplified dependency management and version control

### Added
- **Agentic Orchestration Layer**: New `abi-core add agentic-orchestration-layer` command
  - Adds Planner Agent for task decomposition and agent assignment
  - Adds Orchestrator Agent for multi-agent workflow coordination
  - Automatic agent card generation with cryptographic signing
  - Agent cards include unique authentication tokens (HMAC-SHA256)
  - Cards automatically copied to semantic layer for discovery
  - Planner uses semantic search to find and assign agents
  - Orchestrator performs health checks with exponential backoff retries
  - Workflow execution with LangGraph state machine
  - Result synthesis using LLM for coherent output
  - Web interface for Orchestrator (HTTP/SSE endpoints)
  - Q&A flow between Planner and Orchestrator
  - Prerequisites validation (Guardian + Semantic Layer required)
  - Dynamic port assignment to avoid conflicts
- **Signed Agent Cards**: Agent cards now include authentication credentials
  - Generated at build time with `token_urlsafe(32)`
  - Include `@context`, `@type`, `id`, and `auth` fields
  - HMAC-SHA256 authentication method
  - Unique `key_id` and `shared_secret` per agent
  - Cards are immutable and signed during project setup
  - No runtime initialization needed
  - Semantic layer recognizes cards automatically
- **Model Provisioning Command**: New `abi-core provision-models` command for automated model management
  - Supports both centralized and distributed model serving modes
  - Automatically starts required Docker services (Ollama and agents)
  - Automatically downloads LLM and embedding models
  - Progress tracking and error handling
  - Updates runtime.yaml with provisioning status
  - Idempotent operation (skips already downloaded models)
  - In centralized mode: starts Ollama service automatically
  - In distributed mode: starts agent services (with Ollama) automatically
- **Always-Present Ollama Service**: Ollama service now included in all projects
  - Centralized mode: Single Ollama serves all agents
  - Distributed mode: Ollama serves embeddings, agents have own Ollama
  - Semantic layer always connects to main Ollama service
- **Advanced Guardian Security Service (Guardial)**: Complete security and policy enforcement system
  - Emergency response system with cryptographic signing
  - Real-time security dashboard (web interface)
  - Advanced alerting system with configurable thresholds
  - Comprehensive metrics collection and Prometheus integration
  - Audit persistence with retention policies
  - Secure policy engine with immutable core policies
  - OPA integration with healthchecks and auto-configuration
  - Domain-specific compliance (finance, healthcare)
  - Multi-layer policy evaluation (core + custom policies)
  - Risk scoring with contextual modifiers
- **Automatic Weaviate Integration**: Weaviate vector database now automatically added when using semantic layer
  - Automatically included when creating project with `--with-semantic-layer`
  - Automatically added when running `abi-core add semantic-layer`
  - Proper healthchecks and dependencies configured
  - Persistent volume for vector data
  - No manual configuration required
- **Model Serving Options**: New `--model-serving` flag for `create project` command
  - `centralized`: Single shared Ollama service for all agents (recommended for production)
  - `distributed`: Each agent has its own Ollama instance (default, current behavior)
- Centralized Ollama service template in `compose.yaml.j2` with healthcheck
- `model_serving` configuration field in `runtime.yaml` for persistent project settings
- Dynamic agent configuration in `add agent` command based on project's model serving mode
- Automatic detection and configuration of Ollama connectivity per agent
- Weaviate service tracking in `runtime.yaml` with configuration details

### Changed
- **Default LLM Model**: Changed from `llama3.2:3b` to `qwen2.5:3b` for better tool calling support
  - Excellent function/tool calling capabilities (required for agents)
  - Similar size (~2 GB)
  - Better performance for agent workflows
  - Strong reasoning and instruction following
  - Users can still specify any other model via `--model` flag
- `add agent` command now reads `model_serving` from `runtime.yaml` to configure agents appropriately
- Agent Docker Compose configuration adapts automatically to centralized/distributed mode
- Improved feedback messages showing which model serving mode is being used

### Removed
- **abi_mcp module**: Removed unused MCP client wrapper (not integrated in codebase)
- **agents_d directory**: Removed duplicate scripts (real scripts are in abi-image Docker base)

### Fixed
- Cleaned up unused code and duplicate files in package structure

## [1.0.0] - 2025-01-XX

### Added
- Initial beta release
- Project scaffolding with `create project` command
- Agent creation with `add agent` command
- Semantic layer service support
- Guardian security service support
- OPA policy integration
- A2A protocol support
- MCP server integration
- Docker Compose orchestration
- Agent cards for semantic discovery

### Documentation
- Comprehensive README with examples
- CLI command documentation
- Architecture overview
- Quick start guide

---

## Migration Guide

### Upgrading from 0.1.0b28 to 1.0.0

**No breaking changes** - All existing projects will continue to work as before.

#### New Projects

When creating new projects, you can now choose the model serving strategy:

```bash
# Centralized mode (recommended for production)
abi-core create project my-app --model-serving centralized

# Distributed mode (default, same as before)
abi-core create project my-app --model-serving distributed
# or simply
abi-core create project my-app
```

#### Existing Projects

Existing projects without `model_serving` in their `runtime.yaml` will automatically use `distributed` mode (current behavior). No changes needed.

To migrate an existing project to centralized mode:

1. Edit `.abi/runtime.yaml` and add:
   ```yaml
   project:
     # ... existing fields
     model_serving: "centralized"
   ```

2. Add the centralized Ollama service to your `compose.yaml`:
   ```yaml
   services:
     myproject-ollama:
       image: ollama/ollama:latest
       container_name: myproject-ollama
       ports:
         - "11434:11434"
       volumes:
         - ollama_data:/root/.ollama
       environment:
         - OLLAMA_HOST=0.0.0.0
       networks:
         - myproject-network
       restart: unless-stopped
   
   volumes:
     ollama_data:
       driver: local
   ```

3. Update existing agents to use the centralized service (optional, but recommended):
   - Remove individual Ollama ports (e.g., `11435:11434`)
   - Change `OLLAMA_HOST` to `http://myproject-ollama:11434`
   - Set `START_OLLAMA=false` and `LOAD_MODELS=false`
   - Add `depends_on: [myproject-ollama]`
   - Remove individual `ollama_data` volumes

---

## Model Serving Comparison

| Feature | Centralized | Distributed |
|---------|-------------|-------------|
| Ollama instances | 1 shared | 1 per agent |
| Resource usage | Lower | Higher |
| Model management | Centralized | Per-agent |
| Isolation | Shared | Complete |
| Recommended for | Production | Development |
| Port conflicts | None | Possible |
| Startup time | Faster (agents) | Slower |

---

**Note**: Guardian service always maintains its own Ollama instance for security isolation, regardless of the chosen mode.
