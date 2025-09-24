# ABI Policy Extension Guide

## Overview

ABI Guardian Agent uses Open Policy Agent (OPA) for policy enforcement. The system supports extensible policies from multiple sources.

## Policy Sources (Priority Order)

1. **Built-in Policies** (Highest Priority)
   - Location: `guardial.opa.policies` package
   - Installed with: `pip install abi-core`
   - Contains: Core ABI security policies

2. **Environment Policies**
   - Location: Paths in `ABI_POLICY_PATHS` env var
   - Format: `export ABI_POLICY_PATHS="/path/to/policies1:/path/to/policies2"`

3. **Local Project Policies**
   - Location: `./policies/` directory
   - Use for: Project-specific policies

4. **Installed Policy Packages**
   - Pattern: `*_abi_policies` packages
   - Install with: `pip install company_abi_policies`

## Creating Custom Policies

### 1. Local Policies

Create `.rego` files in your `./policies/` directory:

```rego
# policies/my_custom_policy.rego
package abi.custom

import rego.v1

# Block operations during maintenance
deny if {
    input.action in ["write", "delete"]
    is_maintenance_window
}

is_maintenance_window if {
    hour := time.clock(time.now_ns())[0]
    hour >= 2
    hour <= 4
}
```

### 2. Policy Packages

Create a distributable policy package:

```bash
# Create package structure
mkdir my_company_abi_policies
cd my_company_abi_policies

# Create setup.py
cat > setup.py << EOF
from setuptools import setup, find_packages

setup(
    name="my_company_abi_policies",
    version="1.0.0",
    packages=find_packages(),
    package_data={
        'my_company_abi_policies': ['*.rego'],
    },
)
EOF

# Create policies
mkdir my_company_abi_policies
cat > my_company_abi_policies/company_policies.rego << EOF
package abi.company

# Company-specific policies here
EOF

# Install
pip install .
```

### 3. Environment-Based Policies

```bash
# Set policy paths
export ABI_POLICY_PATHS="/etc/abi/policies:/opt/company/policies"

# ABI will automatically discover and load policies from these paths
```

## Policy Structure

### Required Elements

```rego
package abi.your_namespace

import rego.v1

# Default rules (recommended)
default allow := false
default deny := false
default risk_score := 0.0

# Your policy rules
allow if {
    # conditions for allowing action
}

deny if {
    # conditions for denying action
}

risk_score := score if {
    # calculate risk score (0.0 - 1.0)
}
```

### Input Structure

Policies receive this input structure:

```json
{
    "action": "read|write|delete|execute|agent_communication",
    "resource_type": "document|config|agent_card|system_config",
    "source_agent": "orchestrator|planner|actor|observer|guardial",
    "target_agent": "target_agent_name",
    "content": "content being processed",
    "timestamp": "2025-09-22T10:30:00Z",
    "metadata": {
        "additional": "context"
    }
}
```

## Configuration

### OPA Configuration

Create `config/opa.yaml`:

```yaml
opa:
  url: "http://opa:8181"
  timeout: 30

policies:
  base_path: "./policies"
  auto_reload: true
  bundle_name: "abi"

security:
  fail_safe_mode: "deny"  # deny|allow|warn
  require_opa: true
```

### Environment Variables

```bash
# OPA connection
export OPA_URL="http://localhost:8181"
export OPA_TIMEOUT=30

# Policy paths
export ABI_POLICY_PATHS="./policies:/etc/abi/policies"

# Security settings
export ABI_FAIL_SAFE_MODE="deny"
export ABI_REQUIRE_OPA="true"
```

## Testing Policies

### 1. Policy Validation

```python
from abi_llm_base.opa.policy_loader import PolicyLoader

loader = PolicyLoader()
policies = loader.load_all_policies()
issues = loader.validate_policies()

for issue in issues:
    print(f"Policy {issue['policy']}: {issue['message']}")
```

### 2. Decision Testing

```python
from agent.policy_engine_v2 import get_policy_engine

engine = get_policy_engine()
await engine.initialize()

decision = await engine.evaluate_policy(
    action="write",
    resource_type="config",
    source_agent="test_agent",
    content="test content"
)

print(f"Allow: {decision.allow}, Risk: {decision.risk_score}")
```

## Best Practices

### 1. Policy Organization

```
policies/
├── security/
│   ├── authentication.rego
│   └── authorization.rego
├── compliance/
│   ├── gdpr.rego
│   └── sox.rego
└── operational/
    ├── maintenance.rego
    └── monitoring.rego
```

### 2. Naming Conventions

- Package names: `abi.domain.subdomain`
- Rule names: `descriptive_snake_case`
- Variables: `clear_descriptive_names`

### 3. Documentation

```rego
# Policy: Data Protection
# Purpose: Prevent PII exposure in agent communications
# Author: Security Team
# Version: 1.0

package abi.security.data_protection

# Block messages containing PII patterns
deny if {
    input.action == "agent_communication"
    contains_pii(input.content)
}

contains_pii(content) if {
    # SSN pattern
    regex.match(`\b\d{3}-\d{2}-\d{4}\b`, content)
}
```

## Troubleshooting

### Policy Not Loading

1. Check policy syntax: `opa fmt policies/`
2. Verify package declaration
3. Check file permissions
4. Review logs for errors

### OPA Connection Issues

1. Verify OPA service is running
2. Check network connectivity
3. Validate configuration
4. Review fail-safe settings

### Performance Issues

1. Optimize policy rules
2. Use indexed lookups
3. Cache frequently accessed data
4. Monitor decision latency

## Examples

See `policies/custom_policies.rego` for complete examples of:
- Time-based restrictions
- Agent-specific permissions
- Resource access controls
- Custom risk scoring