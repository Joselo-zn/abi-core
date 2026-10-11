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

User permissions live in the policy the Semantic Layer already uses, `services/guardian/opa/policies/semantic_access.rego` (`package abi.semantic_access`). Edit its `user_permissions` map — one entry per email, with the MCP tools that person may use:

```rego
user_permissions := {
    "admin@company.com": {
        "allowed_tools": ["find_agent", "recommend_agents", "register_agent", "check_agent_capability"],
        "role": "admin"
    },
    "analyst@company.com": {
        "allowed_tools": ["find_agent", "recommend_agents"],
        "role": "user"
    }
}
```

With user validation required, a request is denied when it carries no email, or when the email isn't in the map, or when the tool isn't in that user's `allowed_tools`. `tool_list_agents` calls `recommend_agents`, so list it for anyone who should be able to search for several agents.

Restart OPA after editing — it reads policies at start-up only.

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
