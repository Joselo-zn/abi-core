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

## How Guardian uses OPA

1. Guardian receives a validation request (from Orchestrator or A2A validator)
2. Builds an `input` object with agent info, action, and context
3. POSTs to OPA at `http://opa:8181/v1/data/<package>/allow`
4. OPA evaluates all rules and returns `true` or `false`
5. Guardian returns the decision + any deny reasons

## Next step

👉 [Policy Development](03-policy-development.md)
