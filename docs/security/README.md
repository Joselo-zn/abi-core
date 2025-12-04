# Security Documentation

This directory contains comprehensive documentation for ABI-Core's security features.

## Table of Contents

### 1. [Guardian Service](01-guardian-service.md)
Introduction to the Guardian service - the central security component that enforces policies using Open Policy Agent (OPA).

**Topics covered:**
- What is Guardian
- Architecture overview
- Installation and setup
- Basic configuration
- Health checks and monitoring

### 2. [OPA Policies](02-opa-policies.md)
Understanding Open Policy Agent and how policies work in ABI-Core.

**Topics covered:**
- OPA fundamentals
- Policy structure and syntax
- Built-in policies
- Policy evaluation flow
- Testing policies

### 3. [Policy Development](03-policy-development.md)
Guide to creating and managing custom security policies.

**Topics covered:**
- Writing custom policies
- Policy best practices
- Debugging policies
- Policy versioning
- Deployment strategies

### 4. [User Validation](04-user-validation.md)
User-level access control and validation for semantic layer access.

**Topics covered:**
- User authentication
- User permissions
- Role-based access control (RBAC)
- User validation modes (strict/permissive/disabled)
- Audit logging for user actions

### 5. [Audit & Compliance](05-audit-compliance.md)
Logging, auditing, and compliance features.

**Topics covered:**
- Audit log structure
- Compliance requirements
- Log retention
- Reporting and analytics
- GDPR and privacy considerations

### 6. [A2A Validation](06-a2a-validation.md) ⭐ NEW
Agent-to-Agent communication validation and access control.

**Topics covered:**
- A2A communication overview
- A2AAccessValidator class
- Decorator pattern usage
- OPA policies for A2A
- Communication rules configuration
- Validation modes
- Audit logging for A2A
- Integration examples

**Quick Start:** [A2A Quick Start Guide](A2A-QUICKSTART.md) - 5-minute setup

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ABI-Core Security                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │   Semantic   │      │    Agent     │                │
│  │   Validator  │      │  Validator   │                │
│  │              │      │    (A2A)     │                │
│  └──────┬───────┘      └──────┬───────┘                │
│         │                     │                         │
│         └──────────┬──────────┘                         │
│                    │                                    │
│         ┌──────────▼──────────┐                         │
│         │                     │                         │
│         │     Guardian        │                         │
│         │                     │                         │
│         └──────────┬──────────┘                         │
│                    │                                    │
│         ┌──────────▼──────────┐                         │
│         │                     │                         │
│         │   OPA Policies      │                         │
│         │                     │                         │
│         └──────────┬──────────┘                         │
│                    │                                    │
│         ┌──────────▼──────────┐                         │
│         │                     │                         │
│         │   Audit Logs        │                         │
│         │                     │                         │
│         └─────────────────────┘                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Enable Security Features

```bash
# Enable user validation
export VALIDATION_MODE=strict
export REQUIRE_USER_VALIDATION=true

# Enable A2A validation
export A2A_VALIDATION_MODE=strict
export A2A_ENABLE_AUDIT_LOG=true

# Configure Guardian
export GUARDIAN_URL=http://localhost:8383
export ENABLE_AUDIT_LOG=true
```

### Basic Usage

```python
# User validation
from abi_core.semantic.semantic_access_validator import build_semantic_context_from_card

context = build_semantic_context_from_card(
    agent_card_path="path/to/card.json",
    tool_name="find_agent",
    query="search query",
    user_email="user@example.com"  # User validation
)

# A2A validation
from abi_core.security.a2a_access_validator import validate_a2a_access
from config import AGENT_CARD

target_card = load_agent_card("path/to/target/card.json")

@validate_a2a_access(a2a=(AGENT_CARD, target_card))
async def send_message(message: str):
    # Communication logic
    pass
```

## Security Best Practices

1. **Always use strict mode in production**
   - User validation: `VALIDATION_MODE=strict`
   - A2A validation: `A2A_VALIDATION_MODE=strict`

2. **Enable audit logging**
   - Track all access attempts
   - Monitor for suspicious activity
   - Maintain compliance records

3. **Review policies regularly**
   - Update communication rules
   - Adjust user permissions
   - Remove unused policies

4. **Test policies before deployment**
   - Use OPA playground
   - Write policy tests
   - Validate in staging environment

5. **Monitor Guardian health**
   - Check `/health` endpoint
   - Monitor response times
   - Set up alerts for failures

## Environment Variables Reference

### User Validation
```bash
VALIDATION_MODE=strict|permissive|disabled
REQUIRE_USER_VALIDATION=true|false
REQUIRE_AGENT_VALIDATION=true|false
SEMANTIC_LAYER_DAILY_QUOTA=1000
```

### A2A Validation
```bash
A2A_VALIDATION_MODE=strict|permissive|disabled
A2A_ENABLE_AUDIT_LOG=true|false
```

### Guardian
```bash
GUARDIAN_URL=http://localhost:8383
ENABLE_AUDIT_LOG=true|false
ENABLE_RATE_LIMITING=true|false
```

## Related Documentation

- [Architecture Reference](../reference/architecture.md)
- [Environment Variables](../reference/environment-variables.md)
- [CLI Reference](../reference/cli-reference.md)
- [Production Deployment](../production/04-deployment.md)

## Support

For security-related questions or to report vulnerabilities:
- Email: jl.mrtz@gmail.com
- GitHub Issues: [Report Security Issue](https://github.com/Joselo-zn/abi-core/issues)
