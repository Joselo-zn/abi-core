# Policy Development

Create custom policies for your domain.

## Create Policy

```bash
abi-core add policies trading --domain finance
```

This creates:
```
services/guardian/opa/policies/trading.rego
```

## Policy Structure

```rego
package abi.trading

# Default rule
default allow = false

# Allow small trades
allow if {
    input.action == "execute_trade"
    input.amount < 1000
}

# Require approval for medium trades
require_approval if {
    input.action == "execute_trade"
    input.amount >= 1000
    input.amount < 10000
}

# Deny large trades
deny["Amount exceeds maximum limit"] if {
    input.action == "execute_trade"
    input.amount >= 10000
}
```

## Next Steps

- [Audit and compliance](04-audit-compliance.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
