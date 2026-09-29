# A2A Validation

Controls which agents can talk to which. Uses security rules to decide.

## How it works

```
Agent A calls Agent B
  → System checks the rules: "Is A allowed to talk to B?"
    → Yes? → Message goes through
    → No? → Blocked, error returned, event logged
```

## It's automatic

When you use `agent_connection()`, validation happens transparently:

```python
from abi_core.common.abi_a2a import agent_connection

# This validates against the a2a_access OPA policy before sending
# (no HMAC signature check on this path — that's the Semantic Layer's
# @validate_semantic_access, see "Semantic Layer (MCP) access validation" below)
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
| `strict` | Deny if OPA is unreachable/times out, or if the policy says no |
| `permissive` | Allow if OPA is unreachable/times out, deny only on explicit policy violation |
| `disabled` | Skip validation entirely (development only) |

(The validator, `abi_core.security.a2a_access_validator`, calls OPA directly
— "Guardian" here refers to the Guardian *security layer* this validation is
part of, not an HTTP call to the Guardian agent itself.)

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

```{note}
`input.source_agent.name` / `input.target_agent.name` come straight from each
agent's `AgentCard.name` field — i.e. whatever `name` you put in the agent
card JSON (the scaffolded default policy matches on the full card name, e.g.
`"Abi Orchestrator Agent"`, not a lowercase slug like `"orchestrator"`).
Keep your rules consistent with the actual `name` in your agent cards. The
scaffolded default policy (`abi-core add service guardian`) also uses a
data-driven `communication_rules` list plus a `"*"` wildcard for source/target
instead of one `allow if {}` block per rule — same idea, different shape.
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

## Semantic Layer (MCP) access validation

The mechanism above (`agent_connection` / `AgentInteractionFlow`) validates
**agent-to-agent task delegation** over the A2A protocol. A separate, related
mechanism validates **MCP tool calls into the Semantic Layer** itself — every
built-in tool (`find_agent`, `register_agent`, `search_tool_registry`, ...)
and any custom tool you add (see [Extending the Semantic
Layer](../semantic-layer/04-extending-semantic-layer.md)) can be gated the
same way.

```python
from abi_core.semantic.semantic_access_validator import validate_semantic_access

@mcp.tool(name='my_tool', description='...')
@validate_semantic_access
async def my_tool(query: str, _request_context: dict = None) -> dict:
    ...
```

How it works:

1. **Identity extraction** — reads the agent's identity and signature off the
   MCP request's headers: `X-ABI-Agent-ID`, `X-ABI-Key-Id`, `X-ABI-Signature`,
   `X-ABI-Timestamp`, `X-ABI-Nonce`, and (optionally) `X-ABI-User-Email`. These
   are the same headers `build_semantic_context_from_card()` (see [User
   Validation](04-user-validation.md)) builds for you.
2. **HMAC verification** — if the request carries a payload, the
   `X-ABI-Signature` header is checked against an HMAC-SHA256 of the payload
   signed with the caller's `shared_secret` (`hmac.compare_digest`, constant-time).
3. **Agent card lookup** — loads the caller's agent card by `agent_id`,
   searching `agent_cards/`, `service_cards/`, or `tool_cards/` on disk
   depending on the `agent://`/`service://`/`tool://` prefix. If no static
   card is found, it **falls back to a Weaviate lookup** so a dynamically
   registered card — an ephemeral/zombie agent created at runtime by the
   Builder, not written to disk — is still resolved.
4. **OPA policy evaluation** — POSTs the agent info, agent card, request
   metadata, and (if present) user info to OPA at
   `{OPA_URL}/v1/data/abi/semantic_access` (policy file:
   `services/guardian/opa/policies/semantic_access.rego`, `package
   abi.semantic_access`). The tool only runs if `allow == true` and there are
   no `deny` reasons.

Also enforces, ahead of the OPA call: `VALIDATION_MODE` (`disabled` /
`permissive` / `strict`), `REQUIRE_USER_VALIDATION`, `REQUIRE_AGENT_VALIDATION`,
and a per-agent daily quota (`ENABLE_QUOTA_MANAGEMENT`,
`SEMANTIC_LAYER_DAILY_QUOTA`) — see [User Validation](04-user-validation.md)
for the validation-mode table.

## Next step

👉 [Model Serving](../production/01-model-serving.md)
