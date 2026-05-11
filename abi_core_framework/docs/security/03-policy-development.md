# Policy Development

Write your own Rego policies for your domain.

## Create a policy file

Add a `.rego` file in `services/guardian/opa/policies/`:

```rego
package abi.finance

import future.keywords.if
import future.keywords.in

default allow := false

# Allow read operations for everyone
allow if {
    input.action in ["view_balance", "list_transactions"]
}

# Allow trades only for the finance agent
allow if {
    input.action == "execute_trade"
    input.source_agent.name == "finance_agent"
}

# Require approval for large amounts
require_approval if {
    input.action == "execute_trade"
    input.amount >= 5000
    input.amount < 50000
}

# Hard deny above threshold
deny["Amount exceeds maximum allowed"] if {
    input.action == "execute_trade"
    input.amount >= 50000
}
```

## The input object

OPA receives this from Guardian:

```json
{
  "source_agent": {
    "name": "finance_agent",
    "description": "Handles financial operations"
  },
  "target_agent": {
    "name": "database_agent"
  },
  "action": "execute_trade",
  "amount": 25000,
  "context": {
    "context_id": "session-001",
    "timestamp": "2026-05-11T10:30:00Z"
  }
}
```

You write rules against `input.*`.

## Common patterns

### Time-based access

```rego
allow if {
    input.action == "deploy"
    # Only during business hours (simplified)
    time.clock(time.now_ns())[0] >= 9
    time.clock(time.now_ns())[0] < 17
}
```

### Role-based access

```rego
admin_agents := ["orchestrator", "guardian"]

allow if {
    input.action == "register_agent"
    input.source_agent.name in admin_agents
}
```

### Rate limiting (via metadata)

```rego
deny["Rate limit exceeded"] if {
    input.metadata.requests_last_minute > 100
}
```

## Test locally

```bash
# Check policy syntax
docker exec <opa-container> opa check /policies/

# Evaluate with test input
curl -X POST http://localhost:8181/v1/data/abi/finance/allow \
  -d '{"input": {"action": "execute_trade", "amount": 3000, "source_agent": {"name": "finance_agent"}}}'
```

## Reload policies

OPA watches the policies directory. Changes are picked up automatically. To force:

```bash
docker restart <opa-container>
```

## Next step

👉 [User Validation](04-user-validation.md)
