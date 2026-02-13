# Policy Development Guide

## Overview

ABI-Core uses Open Policy Agent (OPA) for security and governance. Policies are written in Rego and live in the Guardian service at `services/guardian/opa/policies/`.

## Policy Location

When you create a project with Guardian:

```
your-project/
└── services/
    └── guardian/
        └── opa/
            └── policies/          # Your policies go here
                ├── basic.rego
                ├── semantic_access.rego
                └── your_custom.rego    # Add custom policies
```

## Understanding OPA Policies

### Basic Structure

```rego
package abi.your_policy_name

import rego.v1

# Default deny
default allow := false

# Allow rule
allow if {
    # conditions
}

# Deny rules
deny contains "reason" if {
    # violation conditions
}

# Risk calculation
risk_score := score if {
    # calculate score
}
```

### Key Concepts

1. **Package**: Namespace for your policy (e.g., `abi.trading`)
2. **Default**: Default decision (usually `false` for security)
3. **Rules**: Conditions that must be met
4. **Deny**: Explicit denial reasons
5. **Risk Score**: Numerical risk assessment (0.0 to 1.0)

## Built-in Policies

### 1. Semantic Access Policy

Controls agent access to the semantic layer.

**File:** `services/guardian/opa/policies/semantic_access.rego`

**What it does:**
- Verifies agent registration
- Checks blacklist status
- Enforces rate limits
- Validates IP addresses
- Checks access schedules
- Validates MCP tool permissions

**Example input:**
```json
{
  "action": "semantic_layer_access",
  "source_agent": "trader",
  "agent_card": {
    "id": "agent://trader",
    "name": "trader",
    "metadata": {
      "status": "active",
      "trust_level": "high"
    },
    "security": {
      "allowed_ips": ["10.0.0.0/8"],
      "allowed_mcp_tools": ["find_agent", "get_agent_card"]
    }
  },
  "request_metadata": {
    "source_ip": "10.0.1.5",
    "mcp_tool": "find_agent"
  }
}
```

**Example output:**
```json
{
  "allow": true,
  "deny": [],
  "risk_score": 0.2,
  "audit_log": {
    "timestamp": 1705843200000000000,
    "decision": {
      "allow": true,
      "risk_score": 0.2
    }
  }
}
```

### 2. Basic Policy

Template for general access control.

**File:** `services/guardian/opa/policies/basic.rego`

## Creating Custom Policies

### Example 1: Trading Limits Policy

**File:** `services/guardian/opa/policies/trading_limits.rego`

```rego
package abi.trading

import rego.v1

# Default deny
default allow := false
default risk_score := 1.0

# =============================================================================
# TRADING LIMITS
# =============================================================================

# Allow small trades (under $10,000)
allow if {
    input.action == "execute_trade"
    input.trade_amount < 10000
    agent_authorized
}

# Require approval for medium trades ($10,000 - $100,000)
require_approval if {
    input.action == "execute_trade"
    input.trade_amount >= 10000
    input.trade_amount < 100000
}

# Deny large trades (over $100,000)
deny contains "Trade amount exceeds maximum limit" if {
    input.action == "execute_trade"
    input.trade_amount >= 100000
}

# Deny trades outside market hours
deny contains "Trading outside market hours" if {
    input.action == "execute_trade"
    not within_market_hours
}

# Deny if daily limit exceeded
deny contains "Daily trading limit exceeded" if {
    input.action == "execute_trade"
    daily_limit_exceeded
}

# =============================================================================
# AGENT AUTHORIZATION
# =============================================================================

agent_authorized if {
    input.agent_id
    input.agent_id in authorized_trading_agents
}

authorized_trading_agents := {
    "agent://trader",
    "agent://portfolio_manager"
}

# =============================================================================
# MARKET HOURS CHECK
# =============================================================================

within_market_hours if {
    current_hour := time.clock(time.now_ns())[0]
    current_day := time.weekday(time.now_ns())
    
    # Monday-Friday
    current_day >= 1
    current_day <= 5
    
    # 9:30 AM - 4:00 PM EST
    current_hour >= 9
    current_hour < 16
}

# =============================================================================
# DAILY LIMIT CHECK
# =============================================================================

daily_limit_exceeded if {
    input.agent_id
    daily_total := data.daily_trading_totals[input.agent_id]
    daily_limit := 1000000  # $1M daily limit
    
    daily_total + input.trade_amount > daily_limit
}

# =============================================================================
# RISK CALCULATION
# =============================================================================

risk_score := calculated_risk if {
    amount_risk := amount_risk_score
    time_risk := time_risk_score
    agent_risk := agent_risk_score
    
    calculated_risk := min([1.0, amount_risk + time_risk + agent_risk])
}

# Risk by trade amount
amount_risk_score := 0.1 if {
    input.trade_amount < 10000
}

amount_risk_score := 0.5 if {
    input.trade_amount >= 10000
    input.trade_amount < 100000
}

amount_risk_score := 1.0 if {
    input.trade_amount >= 100000
}

# Risk by time
time_risk_score := 0.0 if {
    within_market_hours
}

time_risk_score := 0.3 if {
    not within_market_hours
}

# Risk by agent
agent_risk_score := 0.0 if {
    input.agent_id in trusted_agents
}

agent_risk_score := 0.2 if {
    not input.agent_id in trusted_agents
}

trusted_agents := {
    "agent://trader",
    "agent://portfolio_manager"
}

# =============================================================================
# AUDIT LOG
# =============================================================================

audit_log := {
    "timestamp": time.now_ns(),
    "policy": "trading_limits",
    "version": "1.0.0",
    "decision": {
        "allow": allow,
        "deny": deny,
        "require_approval": require_approval,
        "risk_score": risk_score
    },
    "trade_details": {
        "agent_id": input.agent_id,
        "action": input.action,
        "amount": input.trade_amount,
        "symbol": input.symbol
    }
}
```

### Example 2: Compliance Policy

**File:** `services/guardian/opa/policies/compliance.rego`

```rego
package abi.compliance

import rego.v1

default allow := false

# =============================================================================
# COMPLIANCE CHECKS
# =============================================================================

# Allow if all compliance checks pass
allow if {
    kyc_verified
    not sanctioned_entity
    not high_risk_jurisdiction
    transaction_within_limits
}

# KYC verification
kyc_verified if {
    input.user_id
    data.kyc_status[input.user_id] == "verified"
}

deny contains "KYC verification required" if {
    not kyc_verified
}

# Sanctions screening
sanctioned_entity if {
    input.counterparty
    input.counterparty in data.sanctions_list
}

deny contains "Transaction with sanctioned entity" if {
    sanctioned_entity
}

# Jurisdiction check
high_risk_jurisdiction if {
    input.jurisdiction
    input.jurisdiction in data.high_risk_jurisdictions
}

deny contains "High-risk jurisdiction" if {
    high_risk_jurisdiction
}

# Transaction limits
transaction_within_limits if {
    input.amount
    input.amount <= data.transaction_limits[input.transaction_type]
}

deny contains "Transaction exceeds limits" if {
    not transaction_within_limits
}

# =============================================================================
# RISK SCORING
# =============================================================================

risk_score := score if {
    kyc_risk := kyc_risk_component
    sanctions_risk := sanctions_risk_component
    jurisdiction_risk := jurisdiction_risk_component
    amount_risk := amount_risk_component
    
    score := min([1.0, kyc_risk + sanctions_risk + jurisdiction_risk + amount_risk])
}

kyc_risk_component := 0.0 if kyc_verified
kyc_risk_component := 0.5 if not kyc_verified

sanctions_risk_component := 1.0 if sanctioned_entity
sanctions_risk_component := 0.0 if not sanctioned_entity

jurisdiction_risk_component := 0.3 if high_risk_jurisdiction
jurisdiction_risk_component := 0.0 if not high_risk_jurisdiction

amount_risk_component := score if {
    limit := data.transaction_limits[input.transaction_type]
    ratio := input.amount / limit
    score := min([0.5, ratio * 0.5])
}
```

## Testing Policies

### 1. Test via OPA CLI

```bash
# Enter Guardian OPA container
docker exec -it guardian-opa sh

# Test policy
opa test /app/opa/policies/

# Test specific policy
opa test /app/opa/policies/trading_limits.rego
```

### 2. Test via HTTP API

```bash
# Test trading limits policy
curl -X POST http://localhost:8181/v1/data/abi/trading \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "execute_trade",
      "trade_amount": 5000,
      "agent_id": "agent://trader",
      "symbol": "AAPL"
    }
  }'
```

**Response:**
```json
{
  "result": {
    "allow": true,
    "deny": [],
    "require_approval": false,
    "risk_score": 0.1,
    "audit_log": {
      "timestamp": 1705843200000000000,
      "policy": "trading_limits",
      "decision": {
        "allow": true,
        "risk_score": 0.1
      }
    }
  }
}
```

### 3. Test with Different Scenarios

```bash
# Small trade (should allow)
curl -X POST http://localhost:8181/v1/data/abi/trading \
  -d '{"input": {"action": "execute_trade", "trade_amount": 5000, "agent_id": "agent://trader"}}'

# Medium trade (should require approval)
curl -X POST http://localhost:8181/v1/data/abi/trading \
  -d '{"input": {"action": "execute_trade", "trade_amount": 50000, "agent_id": "agent://trader"}}'

# Large trade (should deny)
curl -X POST http://localhost:8181/v1/data/abi/trading \
  -d '{"input": {"action": "execute_trade", "trade_amount": 150000, "agent_id": "agent://trader"}}'
```

## Policy Best Practices

### 1. Always Default Deny

```rego
# ✅ Good
default allow := false

# ❌ Bad
default allow := true
```

### 2. Provide Clear Denial Reasons

```rego
# ✅ Good
deny contains "Trade amount exceeds maximum limit of $100,000" if {
    input.trade_amount >= 100000
}

# ❌ Bad
deny contains "denied" if {
    input.trade_amount >= 100000
}
```

### 3. Calculate Risk Scores

```rego
# ✅ Good - Granular risk assessment
risk_score := calculated_risk if {
    base_risk := 0.1
    amount_risk := amount_risk_modifier
    time_risk := time_risk_modifier
    calculated_risk := min([1.0, base_risk + amount_risk + time_risk])
}

# ❌ Bad - Binary risk
risk_score := 1.0 if not allow
risk_score := 0.0 if allow
```

### 4. Include Audit Logs

```rego
# ✅ Good
audit_log := {
    "timestamp": time.now_ns(),
    "policy": "trading_limits",
    "decision": {
        "allow": allow,
        "deny": deny,
        "risk_score": risk_score
    },
    "input_summary": {
        "agent_id": input.agent_id,
        "action": input.action,
        "amount": input.trade_amount
    }
}
```

### 5. Use Helper Functions

```rego
# ✅ Good - Reusable helper
is_business_hours if {
    current_hour := time.clock(time.now_ns())[0]
    current_hour >= 9
    current_hour < 17
}

allow if {
    is_business_hours
    # other conditions
}

# ❌ Bad - Repeated logic
allow if {
    current_hour := time.clock(time.now_ns())[0]
    current_hour >= 9
    current_hour < 17
    # other conditions
}
```

## Integrating Policies with Agents

### Python Integration

```python
import httpx
import asyncio

async def check_policy(action: str, data: dict) -> dict:
    """Check policy via OPA"""
    
    opa_url = "http://guardian-opa:8181"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{opa_url}/v1/data/abi/trading",
            json={
                "input": {
                    "action": action,
                    **data
                }
            }
        )
        
        result = response.json()["result"]
        return result

# Usage in agent
async def execute_trade(trade_details):
    """Execute trade with policy check"""
    
    # Check policy
    policy_result = await check_policy("execute_trade", {
        "trade_amount": trade_details["amount"],
        "agent_id": "agent://trader",
        "symbol": trade_details["symbol"]
    })
    
    if not policy_result["allow"]:
        raise PermissionError(f"Trade denied: {policy_result['deny']}")
    
    if policy_result.get("require_approval"):
        return await request_approval(trade_details)
    
    # Execute trade
    return await execute_trade_internal(trade_details)
```

## Policy Data Management

### External Data Sources

Policies can reference external data:

```rego
package abi.trading

# Reference external data
daily_limit_exceeded if {
    input.agent_id
    daily_total := data.daily_trading_totals[input.agent_id]
    daily_limit := data.limits.daily_max
    daily_total + input.trade_amount > daily_limit
}
```

### Updating Data

```bash
# Update data via OPA API
curl -X PUT http://localhost:8181/v1/data/daily_trading_totals \
  -H "Content-Type: application/json" \
  -d '{
    "agent://trader": 500000,
    "agent://portfolio_manager": 750000
  }'

# Update limits
curl -X PUT http://localhost:8181/v1/data/limits \
  -d '{
    "daily_max": 1000000,
    "per_trade_max": 100000
  }'
```

## Monitoring Policies

### View Policy Decisions

```bash
# Get decision logs
curl http://localhost:8181/v1/data/system/log

# Get specific policy decisions
curl http://localhost:8181/v1/data/abi/trading/audit_log
```

### Guardian Dashboard

Access the Guardian dashboard to view:
- Policy evaluation metrics
- Denial reasons
- Risk score trends
- Audit logs

```bash
# Open dashboard
open http://localhost:8080
```

## Advanced Topics

### Multi-Policy Evaluation

Combine multiple policies:

```rego
package abi.combined

import data.abi.trading
import data.abi.compliance

# Allow only if both policies allow
allow if {
    trading.allow
    compliance.allow
}

# Aggregate denials
deny := array.concat(trading.deny, compliance.deny)

# Maximum risk score
risk_score := max([trading.risk_score, compliance.risk_score])
```

### Conditional Policies

Apply policies based on context:

```rego
package abi.conditional

# Different rules for different agent types
allow if {
    input.agent_type == "trader"
    trader_policy_allows
}

allow if {
    input.agent_type == "analyst"
    analyst_policy_allows
}

trader_policy_allows if {
    # trader-specific rules
}

analyst_policy_allows if {
    # analyst-specific rules
}
```

## Troubleshooting

### Policy Not Loading

```bash
# Check OPA logs
docker-compose logs guardian-opa

# Verify policy syntax
docker exec guardian-opa opa check /app/opa/policies/your_policy.rego
```

### Policy Not Evaluating

```bash
# Test policy directly
docker exec guardian-opa opa eval -d /app/opa/policies/ "data.abi.your_policy.allow"

# Check with input
docker exec guardian-opa opa eval -d /app/opa/policies/ -i input.json "data.abi.your_policy"
```

### Unexpected Results

```bash
# Debug policy evaluation
curl -X POST http://localhost:8181/v1/data/abi/trading?explain=full \
  -d '{"input": {...}}'
```

## Next Steps

- [Complete Example](complete-example.md) - See policies in action
- [Agent Development](agent-development.md) - Integrate policies with agents
- [Guardian Service](../architecture.md#guardian) - Learn about Guardian architecture

## Resources

- [OPA Documentation](https://www.openpolicyagent.org/docs/latest/)
- [Rego Language](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [OPA Playground](https://play.openpolicyagent.org/)
