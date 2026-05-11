# A2A Validation

Controls which agents can talk to which. Uses OPA policies via Guardian.

## How it works

```
Agent A calls Agent B
  → A2AAccessValidator checks OPA policy
    → Allowed? → Proceed with communication
    → Denied? → Raise PermissionError, log audit event
```

## It's automatic

When you use `agent_connection()`, validation happens transparently:

```python
from abi_core.common.abi_a2a import agent_connection

# This validates HMAC + OPA policy before sending
async for chunk in agent_connection(my_card, target_card, payload):
    process(chunk)
# Raises PermissionError if denied
```

Same with `AgentInteractionFlow`:

```python
workflow = AgentInteractionFlow()
workflow.set_source_card(AGENT_CARD)  # ← Required for validation
workflow.add_node(node)

async for chunk in workflow.run_workflow():
    # Validation happens per-node before execution
    process(chunk)
```

## Validation modes

Set via `A2A_VALIDATION_MODE` in your agent's config:

| Mode | Behavior |
|------|----------|
| `strict` | Deny if Guardian is unavailable or policy says no |
| `permissive` | Allow if Guardian is unavailable, deny only on explicit policy violation |
| `disabled` | Skip validation entirely (development only) |

## The OPA policy

File: `services/guardian/opa/policies/a2a_access.rego`

```rego
package a2a_access

default allow := false

# Orchestrator can talk to everyone
allow if {
    input.source_agent.name == "orchestrator"
}

# Planner can talk to orchestrator (bidirectional)
allow if {
    input.source_agent.name == "planner"
    input.target_agent.name == "orchestrator"
}

# Everyone can access semantic layer
allow if {
    input.target_agent.name == "semantic-layer"
}

# Block specific pairs
deny if {
    input.source_agent.name == "untrusted"
    input.target_agent.name == "database"
}
```

## Test a policy

```bash
curl -X POST http://localhost:8181/v1/data/a2a_access/allow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "source_agent": {"name": "orchestrator"},
      "target_agent": {"name": "planner"}
    }
  }'
# {"result": true}
```

## Manual validation

If you need to check without making the actual call:

```python
from abi_core.security.a2a_access_validator import get_validator

validator = get_validator()
is_allowed, reason = await validator.validate_a2a_access(
    source_agent_card=my_card,
    target_agent_card=target_card,
    message="test",
)

if not is_allowed:
    print(f"Denied: {reason}")
```

## What gets sent to OPA

```json
{
  "source_agent": {
    "name": "orchestrator",
    "description": "Coordinates workflows",
    "url": "http://orchestrator:8002"
  },
  "target_agent": {
    "name": "planner",
    "description": "Decomposes tasks",
    "url": "http://planner:11437"
  },
  "communication": {
    "timestamp": "2026-05-11T10:30:00Z",
    "message_preview": "Analyze Q4...",
    "message_length": 150
  },
  "validation_mode": "strict"
}
```

## Troubleshooting

**Validation always fails** — Check OPA is running: `curl http://localhost:8181/health`

**Validation always passes** — Check mode isn't `disabled`: look at `A2A_VALIDATION_MODE` in your compose.yaml

**PermissionError on every call** — Your policy might be missing a rule for your agent pair. Test with curl against OPA directly.

## Next step

👉 [Model Serving](../production/01-model-serving.md)
