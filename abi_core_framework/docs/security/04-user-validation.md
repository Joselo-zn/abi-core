# User Validation in Semantic Layer

Learn how to enable and configure user-level access validation for MCP tools.

## Overview

The semantic layer now supports dual validation:
- **Agent validation**: Verifies the agent making the request
- **User validation**: Verifies the user who initiated the request

This ensures that both the agent and the user have appropriate permissions to access resources.

## Configuration

### Validation Modes

Set the validation mode using environment variables:

```bash
# Validation mode: strict/permissive/disabled
VALIDATION_MODE=permissive

# Enable/disable specific validations
REQUIRE_AGENT_VALIDATION=true
REQUIRE_USER_VALIDATION=false
```

#### Modes Explained

1. **`strict`**: Requires both agent AND user validation
   - Agent must be registered with valid signature
   - User email must be provided and authorized
   
2. **`permissive`** (default): Only requires agent validation
   - Agent must be registered with valid signature
   - User email is optional
   
3. **`disabled`**: No validation (development only)
   - All requests are allowed
   - ⚠️ **Never use in production!**

### Environment Variables

**Semantic Layer (`compose.yaml`):**
```yaml
services:
  project-semantic-layer:
    environment:
      # Validation configuration
      - VALIDATION_MODE=permissive
      - REQUIRE_USER_VALIDATION=false
      - REQUIRE_AGENT_VALIDATION=true
      
      # Quota management
      - ENABLE_QUOTA_MANAGEMENT=true
      - SEMANTIC_LAYER_DAILY_QUOTA=1000
      
      # Security
      - GUARDIAN_URL=http://project-guardian:8100
      - OPA_URL=http://project-guardian:8181
```

**Guardian Service:**
```yaml
services:
  project-guardian:
    environment:
      # Validation configuration
      - ENABLE_AGENT_VALIDATION=true
      - ENABLE_USER_VALIDATION=false
      - ENABLE_RESOURCE_VALIDATION=true
      
      # Security
      - REQUIRE_AUTHENTICATION=true
      - ENABLE_AUDIT_LOG=true
```

## Usage

### Including User Email in Requests

When calling MCP tools, include the user email in the context:

```python
from abi_core.security.agent_auth import build_semantic_context_from_card

# Build context with user email
context = build_semantic_context_from_card(
    agent_card_path="/app/agent_cards/my_agent.json",
    tool_name="find_agent",
    query="search query",
    user_email="user@example.com"  # ← User email
)

# Use context in MCP call
result = await mcp_tool(query="...", _request_context=context)
```

### Using MCPToolkit with User Context

```python
from abi_core.common.semantic_tools import MCPToolkit
from abi_core.security.agent_auth import build_semantic_context_from_card

# Create toolkit
toolkit = MCPToolkit()

# Build context with user
context = build_semantic_context_from_card(
    agent_card_path="/app/agent_cards/my_agent.json",
    tool_name="my_custom_tool",
    query="data",
    user_email="user@example.com"
)

# Call tool with context
result = await toolkit.my_custom_tool(
    param="value",
    _request_context=context
)
```

### Web API Integration

When receiving requests from users via web API:

```python
from fastapi import FastAPI, Request
from abi_core.security.agent_auth import build_semantic_context_from_card

app = FastAPI()

@app.post("/query")
async def handle_query(request: Request, query: dict):
    # Extract user email from JWT or session
    user_email = request.state.user.email
    
    # Build context with user
    context = build_semantic_context_from_card(
        agent_card_path="/app/agent_cards/orchestrator.json",
        tool_name="find_agent",
        query=query["text"],
        user_email=user_email
    )
    
    # Process with user context
    result = await process_query(query, context)
    return result
```

## OPA Policies for User Validation

Create policies in `services/guardian/policies/user_access.rego`:

```rego
package abi

# Allow if both agent and user have access
allow {
    agent_has_access
    user_has_access
}

# Validate agent access
agent_has_access {
    input.source_agent
    input.agent_card
    # Agent validation logic...
}

# Validate user access
user_has_access {
    # If user validation not required, allow
    not input.context.require_user_validation
}

user_has_access {
    # If user validation required, check permissions
    input.context.require_user_validation
    input.user.email
    user_has_permission(input.user.email, input.request_metadata.mcp_tool)
}

# User permissions database
user_permissions := {
    "admin@example.com": {
        "allowed_tools": ["find_agent", "register_agent", "list_agents"],
        "role": "admin"
    },
    "user@example.com": {
        "allowed_tools": ["find_agent", "list_agents"],
        "role": "user"
    }
}

# Check if user has permission for tool
user_has_permission(email, tool) {
    perms := user_permissions[email]
    tool in perms.allowed_tools
}

# Deny if user validation required but no email provided
deny["User email required for validation"] {
    input.context.require_user_validation
    not input.user.email
}

# Deny if user doesn't have permission
deny["User does not have permission for this tool"] {
    input.context.require_user_validation
    input.user.email
    not user_has_permission(input.user.email, input.request_metadata.mcp_tool)
}
```

## Testing

### Test with User Validation Disabled

```bash
# Set permissive mode
export VALIDATION_MODE=permissive
export REQUIRE_USER_VALIDATION=false

# Test without user email (should work)
curl -X POST http://localhost:10100/mcp/find_agent \
  -H "Content-Type: application/json" \
  -H "X-ABI-Agent-ID: agent://my_agent" \
  -d '{"query": "search query"}'
```

### Test with User Validation Enabled

```bash
# Set strict mode
export VALIDATION_MODE=strict
export REQUIRE_USER_VALIDATION=true

# Test without user email (should fail)
curl -X POST http://localhost:10100/mcp/find_agent \
  -H "Content-Type: application/json" \
  -H "X-ABI-Agent-ID: agent://my_agent" \
  -d '{"query": "search query"}'

# Test with user email (should work if user has permission)
curl -X POST http://localhost:10100/mcp/find_agent \
  -H "Content-Type: application/json" \
  -H "X-ABI-Agent-ID: agent://my_agent" \
  -H "X-ABI-User-Email: user@example.com" \
  -d '{"query": "search query"}'
```

## Audit Logging

All validation attempts are logged with user information:

```
✅ Semantic access granted for 'agent://planner' | user: user@example.com (risk: 0.20)
❌ Semantic access denied for 'agent://planner' | user: baduser@example.com: User does not have permission for this tool (risk: 0.80)
```

## Best Practices

1. **Start with permissive mode** in development
2. **Enable user validation** in staging/production
3. **Use strict mode** for sensitive operations
4. **Implement proper user authentication** in your web API
5. **Define granular permissions** in OPA policies
6. **Monitor audit logs** for unauthorized access attempts
7. **Rotate secrets regularly** for agent cards

## Migration Guide

### From Agent-Only to Agent+User Validation

1. **Update environment variables:**
   ```bash
   VALIDATION_MODE=strict
   REQUIRE_USER_VALIDATION=true
   ```

2. **Update all MCP calls to include user email:**
   ```python
   # Before
   context = build_semantic_context_from_card(
       agent_card_path=path,
       tool_name="find_agent",
       query=query
   )
   
   # After
   context = build_semantic_context_from_card(
       agent_card_path=path,
       tool_name="find_agent",
       query=query,
       user_email=user.email  # ← Add this
   )
   ```

3. **Create OPA policies for user permissions**

4. **Test thoroughly** before deploying to production

## Troubleshooting

### "User email required for validation"

**Cause**: `REQUIRE_USER_VALIDATION=true` but no email provided

**Solution**: Include `user_email` in `build_semantic_context_from_card()`

### "User does not have permission for this tool"

**Cause**: User email provided but not authorized in OPA policies

**Solution**: Add user to `user_permissions` in OPA policy

### Validation always passes

**Cause**: `VALIDATION_MODE=disabled`

**Solution**: Set to `permissive` or `strict`

## Next Steps

- [OPA Policies](02-opa-policies.md) - Learn about policy development
- [Guardian Service](01-guardian-service.md) - Configure Guardian
- [Audit & Compliance](04-audit-compliance.md) - Monitor access

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
