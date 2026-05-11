# User Validation

Beyond agent-level security, you can validate the human user behind a request.

## Validation modes

Set via environment variable `VALIDATION_MODE`:

| Mode | Agent auth | User auth | Use case |
|------|-----------|-----------|----------|
| `disabled` | ❌ | ❌ | Local development only |
| `permissive` | ✅ | Optional | Default — agents must authenticate, users optional |
| `strict` | ✅ | ✅ | Production — both agent and user must be validated |

## Include user context

When building MCP calls, pass the user email:

```python
from abi_core.security.agent_auth import build_semantic_context_from_card

context = build_semantic_context_from_card(
    agent_card_path="/app/agent_cards/my_agent.json",
    tool_name="find_agent",
    query="search query",
    user_email="user@example.com",  # ← Identifies the human user
)
```

## OPA policy for user permissions

```rego
package abi

# User permission database
user_permissions := {
    "admin@company.com": {"role": "admin", "tools": ["*"]},
    "analyst@company.com": {"role": "user", "tools": ["find_agent", "search_tools"]},
}

# Allow if user has permission for this tool
allow if {
    perms := user_permissions[input.user.email]
    "*" in perms.tools
}

allow if {
    perms := user_permissions[input.user.email]
    input.request_metadata.mcp_tool in perms.tools
}

# Deny if user not found
deny["User not authorized"] if {
    input.context.require_user_validation
    not user_permissions[input.user.email]
}
```

## Configure in compose.yaml

```yaml
services:
  my-semantic-layer:
    environment:
      - VALIDATION_MODE=strict
      - REQUIRE_USER_VALIDATION=true
      - REQUIRE_AGENT_VALIDATION=true
```

## Next step

👉 [Audit & Compliance](05-audit-compliance.md)
