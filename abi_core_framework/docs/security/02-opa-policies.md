# OPA Policies

OPA is the rules engine. You write rules in a language called Rego. Guardian asks OPA "is this allowed?" and OPA answers yes or no.

## Where policies live

```
services/guardian/opa/policies/
├── a2a_access.rego      ← Agent-to-agent communication rules
├── semantic_access.rego ← Who can use which MCP tools
└── custom.rego          ← Your domain-specific rules
```

## A simple policy

```rego
package abi.custom

default allow = false

# Allow all requests from the orchestrator
allow if {
    input.source_agent.name == "orchestrator"
}

# Allow only small transactions
allow if {
    input.action == "execute_trade"
    input.amount < 10000
}

# Deny with a reason
deny["Transaction exceeds limit"] if {
    input.action == "execute_trade"
    input.amount >= 10000
}
```

## Test a policy

```bash
curl -X POST http://localhost:8181/v1/data/abi/custom/allow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "source_agent": {"name": "orchestrator"},
      "action": "execute_trade",
      "amount": 5000
    }
  }'
```

Response: `{"result": true}`

## Who talks to OPA

OPA is a shared rules engine, not something every request is proxied
through Guardian to reach — three independent pieces call it directly with
`httpx`, each building its own `input` object and hitting its own package:

| Caller | Package | Used for |
|--------|---------|----------|
| Guardian's own DAG (`evaluate_policy` step, via `policy_engine_secure`) | your custom policies (e.g. `abi.custom`, `abi.finance`) + core policies | Direct action validation requested over A2A (`guardian_validate` in the Orchestrator's DAG) or workflow validation |
| `abi_core.security.a2a_access_validator` | `a2a_access` | Agent-to-agent task delegation (`agent_connection`, `AgentInteractionFlow`) — see [A2A Validation](06-a2a-validation.md) |
| `abi_core.semantic.semantic_access_validator` | `abi.semantic_access` | MCP tool calls into the Semantic Layer — see [A2A Validation → Semantic Layer access validation](06-a2a-validation.md#semantic-layer-mcp-access-validation) |

Each caller:

1. Builds an `input` object with agent info, action/tool, and context
2. POSTs to OPA at `http://opa:8181/v1/data/<package>/allow` (or `/<package>`
   for a package that returns a richer object, like `abi.semantic_access`)
3. OPA evaluates all rules and returns the result
4. The caller applies its own decision (deny/allow, `strict`/`permissive`
   fallback on OPA being unreachable). Only the A2A validator additionally
   reports the outcome to Guardian's `/audit/log` for the audit trail — a
   separate call from the policy check itself. The semantic-access
   validator only logs locally (`abi_logging`); it accepts a `guardian_url`
   but doesn't currently call it.

## Next step

👉 [Policy Development](03-policy-development.md)
