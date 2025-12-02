# Documentation Updates - Agentic Orchestration Layer

## Summary

Updated ABI-Core documentation to reflect the new **Agentic Orchestration Layer** capabilities, including Planner and Orchestrator agents, signed agent cards, and multi-agent workflow coordination.

## Files Updated

### 1. CHANGELOG.md
**Changes:**
- Added "Agentic Orchestration Layer" section under [Unreleased]
- Documented new `abi-core add agentic-orchestration-layer` command
- Documented signed agent cards with cryptographic authentication
- Listed all features: Planner, Orchestrator, agent card generation, workflow execution

### 2. docs/index.md
**Changes:**
- Added "Agentic Orchestration" to Features section
- Added new documentation pages to table of contents:
  - `user-guide/agent-cards`
  - `user-guide/multi-agent-workflows`
  - `user-guide/planner-orchestrator-integration`

### 3. docs/getting-started/quickstart.md
**Changes:**
- Updated workflow to include orchestration layer setup
- Added section "Add Orchestration Layer"
- Updated "Add Worker Agents" section with agent card registration
- Added "Test Multi-Agent Workflow" example
- Updated project structure to show Planner and Orchestrator
- Added orchestration commands to "Common Commands"

### 4. docs/user-guide/cli-reference.md
**Changes:**
- Added complete documentation for `add agentic-orchestration-layer` command
- Documented prerequisites (Guardian + Semantic Layer)
- Documented what the command creates (agents, cards, configuration)
- Added agent capabilities (Planner and Orchestrator)
- Added usage examples with curl commands
- Updated "Create Complete Project" workflow to include orchestration
- Added multi-agent query example

### 5. docs/user-guide/planner-orchestrator-integration.md
**Changes:**
- Updated "Configuration" section with agent card details
- Added "Agent Card Security" subsection
- Documented authentication method (HMAC-SHA256)
- Added link to Agent Cards Guide

### 6. docs/user-guide/agent-cards.md (NEW)
**Content:**
- Complete guide to agent cards
- JSON-LD structure explanation
- Key fields documentation (identity, connectivity, capabilities, tasks, skills, auth, metadata)
- Automatic generation process
- Authentication with HMAC-SHA256
- Semantic discovery mechanism
- Card lifecycle (generation, storage, registration, discovery, authentication)
- Best practices
- Troubleshooting guide
- Examples (minimal and complete cards)

### 7. docs/user-guide/multi-agent-workflows.md (NEW)
**Content:**
- Complete multi-agent workflow guide
- Architecture diagram
- Four workflow phases:
  1. Task Decomposition (Planner)
  2. Agent Discovery (Semantic Search)
  3. Workflow Execution (Orchestrator)
  4. Result Synthesis (LLM)
- Execution strategies (sequential, parallel, hybrid)
- Complete example with setup and execution
- Error handling patterns
- Best practices
- Monitoring and logging
- Troubleshooting guide

## New Capabilities Documented

### 1. Agentic Orchestration Layer
- **Command**: `abi-core add agentic-orchestration-layer`
- **Components**: Planner Agent + Orchestrator Agent
- **Prerequisites**: Guardian + Semantic Layer
- **Ports**: Planner (11437), Orchestrator (8002 A2A, 8083 Web)

### 2. Planner Agent
- Task decomposition with Chain of Thought
- Semantic agent discovery via MCP tools
- Clarification question generation
- Dependency management
- Execution strategy selection

### 3. Orchestrator Agent
- Workflow execution with LangGraph
- Agent health monitoring with retries
- Progress streaming (every 5 seconds)
- Result synthesis with LLM
- Q&A handling between agents
- Web interface (HTTP/SSE)

### 4. Signed Agent Cards
- Generated at build time
- HMAC-SHA256 authentication
- Unique `shared_secret` per agent (32-byte token)
- Immutable and persistent
- Automatic registration with semantic layer
- No runtime initialization needed

### 5. Multi-Agent Workflows
- Sequential execution
- Parallel execution
- Hybrid execution
- Dependency management
- Health checks with exponential backoff
- Progress tracking
- Result synthesis

## Documentation Structure

```
docs/
├── index.md                                    # Updated
├── CHANGELOG.md                                # Updated
├── getting-started/
│   └── quickstart.md                          # Updated
└── user-guide/
    ├── cli-reference.md                       # Updated
    ├── agent-cards.md                         # NEW
    ├── multi-agent-workflows.md               # NEW
    └── planner-orchestrator-integration.md    # Updated
```

## Key Sections Added

### CLI Reference
- `add agentic-orchestration-layer` command documentation
- Prerequisites verification
- Agent capabilities
- Usage examples
- Updated complete project workflow

### Agent Cards Guide
- Structure and fields
- Automatic generation
- Authentication (HMAC-SHA256)
- Semantic discovery
- Lifecycle management
- Best practices
- Troubleshooting

### Multi-Agent Workflows Guide
- Architecture overview
- Four workflow phases
- Execution strategies
- Complete example
- Error handling
- Monitoring
- Troubleshooting

## Examples Added

### 1. Add Orchestration Layer
```bash
abi-core add agentic-orchestration-layer
```

### 2. Query Orchestrator
```bash
curl -X POST http://localhost:8083/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "analyze customer data and generate report",
    "context_id": "session-001",
    "task_id": "task-001"
  }'
```

### 3. Complete Project Setup
```bash
# Create project
abi-core create project fintech-ai \
  --with-semantic-layer \
  --with-guardian

# Add orchestration
abi-core add agentic-orchestration-layer

# Add workers
abi-core add agent trader
abi-core add agent-card trader --tasks "execute_trade,cancel_order"

# Start
abi-core run
```

## Next Steps for ReadTheDocs

1. **Commit changes** to repository
2. **Push to main branch**
3. **ReadTheDocs will auto-build** from latest commit
4. **Verify build** at https://readthedocs.org/projects/abi-core/

## Build Verification

To verify documentation builds correctly:

```bash
cd docs
pip install -r requirements.txt
make html
```

Check output in `docs/_build/html/index.html`

## Notes

- All new documentation follows existing style and format
- Cross-references added between related documents
- Examples are complete and tested
- Troubleshooting sections included
- Best practices documented
- No breaking changes to existing documentation


---

## Update 2024-11-29: MCPToolkit Documentation

### Summary

Added comprehensive documentation for **MCPToolkit**, a new pythonic interface for calling custom MCP tools dynamically. This update provides developers with an easier way to interact with the semantic layer's MCP server.

### Files Created

#### 1. docs/semantic-layer/05-mcp-toolkit.md (NEW)
**Content:**
- Complete guide to MCPToolkit usage
- Comparison: with vs without MCPToolkit
- Basic usage examples (dynamic and explicit calls)
- Tool discovery methods (list_tools, has_tool)
- Error handling patterns
- 7 real-world examples:
  - Data processing pipeline
  - Conditional tool execution
  - Batch processing
  - Using in agent code
  - Custom configuration
  - Debugging
  - Creating custom MCP tools
- Best practices section
- Advanced usage patterns
- Troubleshooting guide
- Integration with LangChain

#### 2. examples/mcp_toolkit_usage.py (NEW)
**Content:**
- Complete working examples of MCPToolkit
- 7 example functions demonstrating different use cases
- Async/await patterns
- Error handling examples
- Batch processing examples
- Real-world data pipeline scenario

### Files Updated

#### 1. docs/semantic-layer/01-what-is-semantic-layer.md
**Changes:**
- Added "Option 1: Using MCPToolkit (Recommended)" section
- Showed MCPToolkit as the preferred way to interact with semantic layer
- Kept existing client.py examples as "Option 2"
- Added link to MCPToolkit documentation in "Next Steps"

#### 2. docs/semantic-layer/02-agent-discovery.md
**Changes:**
- Added "Using MCPToolkit (Recommended)" section with examples
- Demonstrated find_agent, recommend_agents, check_agent_capability, check_agent_health
- Kept existing client examples as alternative
- Added link to MCPToolkit documentation

#### 3. docs/semantic-layer/04-extending-semantic-layer.md
**Changes:**
- Added "Create Custom MCP Tools" section
- Showed how to create tools that work with MCPToolkit
- Demonstrated @server.call_tool() decorator pattern
- Added example of calling custom tools via MCPToolkit
- Added link to MCPToolkit documentation in "Next Steps"

#### 4. docs/index.md
**Changes:**
- Added `semantic-layer/05-mcp-toolkit` to table of contents
- Integrated into "4. Semantic Layer" section

### Key Features Documented

1. **Dynamic Tool Access**
   - Pythonic syntax: `await toolkit.my_tool(param="value")`
   - Attribute-based access via `__getattr__`
   - Explicit call method for dynamic tool names

2. **Tool Discovery**
   - `list_tools()` - List all available MCP tools
   - `has_tool(name)` - Check if specific tool exists
   - Tool caching for performance

3. **Error Handling**
   - Structured error responses
   - Try-except patterns
   - Graceful degradation examples

4. **Integration Patterns**
   - Using in agent code
   - Data processing pipelines
   - Batch processing
   - Conditional execution

5. **Best Practices**
   - Reuse toolkit instances
   - Check tool availability
   - Handle errors gracefully
   - Use type hints

### Benefits for Developers

- **Reduced Boilerplate**: No need to manually manage MCP sessions
- **Pythonic API**: Natural Python syntax for tool calls
- **Type Safety**: Consistent return types (always dict)
- **Better DX**: Clear error messages and logging
- **Flexibility**: Supports both dynamic and explicit calling patterns

### Code Examples Added

- 7 complete working examples in documentation
- Full example file with async patterns
- Real-world scenarios (data pipelines, batch processing)
- Integration with agent code
- Custom tool creation guide

### Related Implementation

This documentation update corresponds to the implementation of:
- `MCPToolkit` class in `src/abi_core/common/semantic_tools.py`
- Updated `custom_tool` function in `src/abi_core/abi_mcp/client.py`
- Global `mcp_toolkit` instance for convenience

### Next Steps for Users

After reading this documentation, users can:
1. Replace manual MCP client calls with MCPToolkit
2. Create custom MCP tools for their semantic layer
3. Build data processing pipelines with MCP tools
4. Integrate MCP tools seamlessly into their agents

---

**Documentation Author**: José Luis Martínez  
**Date**: 2024-11-29  
**Related PR**: MCPToolkit Implementation


---

## Update 2024-12-02: Configuration Centralization & User Validation

### Summary

Implemented centralized configuration for Semantic Layer and Guardian services, and added comprehensive user-level validation for MCP tool access.

### Files Created

#### 1. Configuration Files

**Semantic Layer Configuration:**
- `src/abi_core/scaffolding/service_semantic_layer/config/config.py.j2`
- `src/abi_core/scaffolding/service_semantic_layer/config/__init__.py.j2`

**Guardian Configuration:**
- `src/abi_core/scaffolding/service_guardian/config/config.py.j2`
- `src/abi_core/scaffolding/service_guardian/config/__init__.py.j2`

**Documentation:**
- `docs/security/04-user-validation.md` - Complete guide for user validation

### Files Updated

#### 1. Semantic Layer Service

**main.py.j2:**
- Imports `config` module instead of using `os.getenv()` directly
- Displays configuration on startup
- Uses `config.HOST`, `config.PORT`, `config.TRANSPORT`

**server.py.j2:**
- Imports `config` module
- Uses `config.EMBEDDING_MODEL` instead of `os.getenv("MODEL")`

#### 2. Guardian Service

**main.py.j2:**
- Imports `config` module
- Uses `config.HOST` and `config.PORT` for dashboard

**guardial_secure.py.j2:**
- Imports `config` module
- Uses `config.MODEL_NAME` instead of `os.getenv("MODEL_NAME")`

#### 3. Security & Validation

**agent_auth.py:**
- Added `user_email` parameter to `build_semantic_context_from_card()`
- Includes user email in payload and headers
- Maintains backward compatibility (user_email is optional)

**semantic_access_validator.py:**
- Added configuration import with fallback to environment variables
- Implemented `_extract_user_info()` method
- Updated `validate_access()` to support user validation
- Added validation modes: `strict`, `permissive`, `disabled`
- Updated `_prepare_opa_input()` to include user information
- Enhanced logging to include user email

**semantic_access.rego:**
- Added USER VALIDATION section
- Implemented `user_validation_passed` rule
- Added `user_has_access` verification
- Included `user_permissions` database
- Added user-specific deny rules
- Updated audit log with user information
- Added user-related remediation suggestions

### Configuration Variables

#### Semantic Layer Config

**Validation:**
- `REQUIRE_USER_VALIDATION` - Enable/disable user validation (default: false)
- `REQUIRE_AGENT_VALIDATION` - Enable/disable agent validation (default: true)
- `VALIDATION_MODE` - strict/permissive/disabled (default: permissive)

**Quotas:**
- `SEMANTIC_LAYER_DAILY_QUOTA` - Daily request limit (default: 1000)
- `ENABLE_QUOTA_MANAGEMENT` - Enable quota tracking (default: true)

**Security:**
- `GUARDIAN_URL` - Guardian service URL
- `OPA_URL` - OPA policy engine URL
- `VALIDATION_CACHE_TTL` - Cache duration in seconds (default: 300)

**Weaviate:**
- `WEAVIATE_HOST` - Weaviate server URL
- `WEAVIATE_ENABLED` - Enable/disable Weaviate (default: true)

**Embedding:**
- `EMBEDDING_MODEL` - Model for embeddings (default: nomic-embed-text:v1.5)
- `OLLAMA_HOST` - Ollama server URL

#### Guardian Config

**Validation:**
- `ENABLE_AGENT_VALIDATION` - Enable agent validation (default: true)
- `ENABLE_USER_VALIDATION` - Enable user validation (default: false)
- `ENABLE_RESOURCE_VALIDATION` - Enable resource validation (default: true)

**Security:**
- `REQUIRE_AUTHENTICATION` - Require authentication (default: true)
- `ENABLE_AUDIT_LOG` - Enable audit logging (default: true)
- `AUDIT_LOG_PATH` - Path to audit log file

**Rate Limiting:**
- `ENABLE_RATE_LIMITING` - Enable rate limiting (default: true)
- `RATE_LIMIT_REQUESTS` - Max requests per window (default: 100)
- `RATE_LIMIT_WINDOW` - Time window in seconds (default: 60)

**Risk Scoring:**
- `ENABLE_RISK_SCORING` - Enable risk scoring (default: true)
- `HIGH_RISK_THRESHOLD` - High risk threshold (default: 0.7)
- `MEDIUM_RISK_THRESHOLD` - Medium risk threshold (default: 0.4)

**Policies:**
- `POLICIES_DIR` - Directory for OPA policies
- `AUTO_RELOAD_POLICIES` - Auto-reload policies (default: true)
- `POLICY_RELOAD_INTERVAL` - Reload interval in seconds (default: 60)

**AI Assistance:**
- `ENABLE_AI_POLICY_ASSIST` - Enable AI policy assistance (default: false)
- `MODEL_NAME` - LLM model for AI assistance
- `OLLAMA_HOST` - Ollama server URL

### Validation Modes

**1. `disabled`:**
- No validation performed
- All requests allowed
- ⚠️ Development only - never use in production

**2. `permissive` (default):**
- Agent validation required
- User validation optional
- Backward compatible with existing code

**3. `strict`:**
- Both agent AND user validation required
- User email must be provided
- Highest security level

### Usage Examples

#### Basic Usage with User Email

```python
from abi_core.security.agent_auth import build_semantic_context_from_card

# Build context with user email
context = build_semantic_context_from_card(
    agent_card_path="/app/agent_cards/my_agent.json",
    tool_name="find_agent",
    query="search query",
    user_email="user@example.com"  # ← User email
)

# Use in MCP call
result = await mcp_tool(query="...", _request_context=context)
```

#### Configuration in compose.yaml

```yaml
services:
  project-semantic-layer:
    environment:
      # Validation mode
      - VALIDATION_MODE=permissive
      - REQUIRE_USER_VALIDATION=false
      - REQUIRE_AGENT_VALIDATION=true
      
      # Quotas
      - ENABLE_QUOTA_MANAGEMENT=true
      - SEMANTIC_LAYER_DAILY_QUOTA=1000
      
      # Security
      - GUARDIAN_URL=http://project-guardian:8100
      - OPA_URL=http://project-guardian:8181

  project-guardian:
    environment:
      # Validation
      - ENABLE_AGENT_VALIDATION=true
      - ENABLE_USER_VALIDATION=false
      
      # Security
      - REQUIRE_AUTHENTICATION=true
      - ENABLE_AUDIT_LOG=true
      
      # Rate limiting
      - ENABLE_RATE_LIMITING=true
      - RATE_LIMIT_REQUESTS=100
```

### OPA Policy Updates

The `semantic_access.rego` policy now includes:

1. **User Validation Rules:**
   - `user_validation_passed` - Main validation rule
   - `user_has_access` - Permission checking
   - `user_permissions` - User permission database

2. **User-Specific Deny Rules:**
   - "User email required for validation"
   - "User does not have permission for this tool"

3. **Enhanced Audit Log:**
   - Includes user email
   - Tracks validation mode
   - Records user validation requirements

4. **Remediation Suggestions:**
   - "Provide user email in request context"
   - "Request tool access permission from administrator"

### Benefits

1. **Centralized Configuration:**
   - Single source of truth for service settings
   - Easy to manage and update
   - Type-safe configuration access
   - Display configuration on startup

2. **User-Level Security:**
   - Fine-grained access control per user
   - Audit trail includes user information
   - Flexible permission management
   - Role-based access control ready

3. **Flexible Validation:**
   - Three validation modes for different environments
   - Easy to enable/disable features
   - Backward compatible
   - Production-ready security

4. **Better Observability:**
   - Configuration displayed on startup
   - User information in logs
   - Enhanced audit trail
   - Clear error messages

### Migration Path

**Phase 1: Development (Current)**
```bash
VALIDATION_MODE=permissive
REQUIRE_USER_VALIDATION=false
```

**Phase 2: Staging**
```bash
VALIDATION_MODE=permissive
REQUIRE_USER_VALIDATION=true
```

**Phase 3: Production**
```bash
VALIDATION_MODE=strict
REQUIRE_USER_VALIDATION=true
```

### Testing

**Test User Validation:**
```bash
# Without user email (should fail in strict mode)
curl -X POST http://localhost:10100/mcp/find_agent \
  -H "X-ABI-Agent-ID: agent://my_agent" \
  -d '{"query": "search"}'

# With user email (should work if user has permission)
curl -X POST http://localhost:10100/mcp/find_agent \
  -H "X-ABI-Agent-ID: agent://my_agent" \
  -H "X-ABI-User-Email: user@example.com" \
  -d '{"query": "search"}'
```

### Related Files

**Implementation:**
- `src/abi_core/security/agent_auth.py`
- `src/abi_core/semantic/semantic_access_validator.py`
- `src/abi_core/scaffolding/service_guardian/opa/policies/semantic_access.rego`

**Configuration:**
- `src/abi_core/scaffolding/service_semantic_layer/config/config.py.j2`
- `src/abi_core/scaffolding/service_guardian/config/config.py.j2`

**Documentation:**
- `docs/security/04-user-validation.md`

---

**Documentation Author**: José Luis Martínez  
**Date**: 2024-12-02  
**Related PR**: Configuration Centralization & User Validation
