# OPA Policies

OPA (Open Policy Agent) evaluates security policies in real-time.

## What is OPA?

OPA is a policy engine that decides:
- Can this agent do this action?
- Does it comply with business rules?
- Is it safe to proceed?

## Policy Example

```rego
package abi.custom

# Allow only during business hours
allow if {
    input.action == "execute_trade"
    time.now_ns() >= business_hours_start
    time.now_ns() <= business_hours_end
}

# Deny large transactions
deny["Amount exceeds limit"] if {
    input.action == "execute_trade"
    input.amount > 10000
}
```

## Test Policy

```bash
curl -X POST http://localhost:8181/v1/data/abi/custom \
  -d '{
    "input": {
      "action": "execute_trade",
      "amount": 5000
    }
  }'
```

## Next Steps

- [Policy development](03-policy-development.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
