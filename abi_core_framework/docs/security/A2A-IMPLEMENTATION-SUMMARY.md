# A2A Validation - Implementation Summary

## Overview

A2A (Agent-to-Agent) validation is now fully integrated into ABI-Core, providing automatic security validation for all agent communications.

## What Was Implemented

### 1. Core Validation System

**File:** `src/abi_core/security/a2a_access_validator.py` (312 lines)

- `A2AAccessValidator` class with 3 validation modes
- `get_validator()` function with smart config detection
- `@validate_a2a_access` decorator for manual validation
- Automatic fallback from config.py to environment variables
- Full audit logging support

### 2. Automatic Integration

**File:** `src/abi_core/common/abi_a2a.py` (104 lines)

- `agent_connection()` function for all A2A communications
- Automatic validation before establishing connection
- Extracts message for logging and audit
- Raises `PermissionError` on denial
- Detailed logging with emojis (✅ ❌ ⚠️)

### 3. Workflow Integration

**File:** `src/abi_core/common/workflow.py`

- `run_node()` updated to accept `source_card` parameter
- Calls `agent_connection()` with both source and target cards
- `set_source_card()` method to configure source agent
- Automatic validation in workflow execution

### 4. OPA Policy

**File:** `src/abi_core/scaffolding/service_guardian/opa/policies/a2a_access.rego` (130 lines)

- Complete policy for A2A access control
- Configurable communication rules
- Wildcard support (`*`)
- Bidirectional communication support
- Detailed deny reasons

### 5. Configuration

**Files:**
- `src/abi_core/scaffolding/agent/config/config.py.j2` (template)
- `src/abi_core/abi_agents/orchestrator/agent/config/config.py`
- `src/abi_core/abi_agents/planner/agent/config/config.py`

**Variables added:**
```python
A2A_VALIDATION_MODE: str = os.getenv('A2A_VALIDATION_MODE', 'strict')
A2A_ENABLE_AUDIT_LOG: bool = os.getenv('A2A_ENABLE_AUDIT_LOG', 'true').lower() == 'true'
GUARDIAN_URL: str = os.getenv('GUARDIAN_URL', 'http://project-guardian:8383')
```

### 6. Documentation

- **Full Guide:** `docs/security/06-a2a-validation.md` (9KB)
- **Quick Start:** `docs/security/A2A-QUICKSTART.md` (3KB)
- **Security Index:** `docs/security/README.md` (updated)
- **Main Index:** `docs/index.md` (updated)

### 7. Examples

- **Basic Usage:** `examples/a2a_validator_usage.py` (213 lines)
- **Full Integration:** `examples/a2a_integration_example.py` (new)

## How It Works

### Automatic Flow

```
1. Orchestrator creates workflow
2. Calls workflow.set_source_card(AGENT_CARD)
3. Workflow executes nodes
4. Each node calls agent_connection(source_card, target_card, payload)
5. agent_connection() validates via A2AAccessValidator
6. Validator checks with Guardian/OPA
7. If allowed: connection proceeds
8. If denied: PermissionError raised
9. All attempts logged to audit
```

### Configuration Flow

```
1. Agent starts
2. config.py loads environment variables
3. A2AAccessValidator.get_validator() called
4. Tries to import config from agent
5. If successful: uses config.A2A_VALIDATION_MODE, etc.
6. If fails: falls back to os.getenv()
7. Validator configured and ready
```

## Validation Modes

### strict (Production)
- ✅ Validates all communications
- ❌ Denies on Guardian error
- ❌ Denies on policy violation
- 📝 Full audit logging

### permissive (Development)
- ✅ Validates all communications
- ✅ Allows on Guardian error
- ❌ Denies only on explicit policy violation
- 📝 Full audit logging

### disabled (Testing Only)
- ⚠️ No validation
- ✅ Allows all traffic
- ⚠️ No Guardian calls
- ⚠️ No audit logs

## Usage Examples

### In Orchestrator

```python
from config import config, AGENT_CARD
from abi_core.common.workflow import WorkflowGraph, WorkflowNode

# Create workflow
workflow = WorkflowGraph()

# Add nodes
node = WorkflowNode(task="Process data", agent_card=target_agent_card)
workflow.add_node(node)

# Configure source (IMPORTANT!)
workflow.set_source_card(AGENT_CARD)

# Execute - validation automatic
async for chunk in workflow.run_workflow():
    process(chunk)
```

### Manual Validation

```python
from abi_core.security.a2a_access_validator import get_validator
from config import AGENT_CARD

validator = get_validator()

is_allowed, reason = await validator.validate_a2a_access(
    source_agent_card=AGENT_CARD,
    target_agent_card=target_card,
    message="Test message"
)

if not is_allowed:
    print(f"Denied: {reason}")
```

### Configure Policy

```rego
# services/guardian/opa/policies/a2a_access.rego

communication_rules := [
    # Orchestrator can talk to everyone
    {"source": "orchestrator", "target": "*", "bidirectional": false},
    
    # Specific pairs
    {"source": "data-agent", "target": "analytics-agent", "bidirectional": true},
    
    # All can access semantic layer
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
]
```

## Environment Configuration

### Docker Compose

```yaml
services:
  my-orchestrator:
    environment:
      - A2A_VALIDATION_MODE=strict
      - A2A_ENABLE_AUDIT_LOG=true
      - GUARDIAN_URL=http://my-project-guardian:8383
```

### .env File

```bash
A2A_VALIDATION_MODE=strict
A2A_ENABLE_AUDIT_LOG=true
GUARDIAN_URL=http://localhost:8383
```

## Testing

### Unit Tests

```python
import os
os.environ['A2A_VALIDATION_MODE'] = 'disabled'

# Your tests here - no validation
```

### Integration Tests

```python
os.environ['A2A_VALIDATION_MODE'] = 'permissive'

# Tests with validation but flexible on errors
```

### Production

```bash
A2A_VALIDATION_MODE=strict
```

## Troubleshooting

### "source_card not provided"

**Solution:** Add `workflow.set_source_card(AGENT_CARD)` before running

### "Guardian timeout"

**Solutions:**
1. Check Guardian is running: `docker ps | grep guardian`
2. Verify GUARDIAN_URL in config
3. Use `permissive` mode in development

### "Communication not allowed"

**Solution:** Add rule to `a2a_access.rego`:
```rego
{"source": "your-agent", "target": "target-agent", "bidirectional": false}
```

## Next Steps

1. ✅ Implementation complete
2. ⏳ Test in real project
3. ⏳ Adjust policies as needed
4. ⏳ Monitor audit logs
5. ⏳ Fine-tune validation rules

## Related Documentation

- [Full A2A Documentation](06-a2a-validation.md)
- [Quick Start Guide](A2A-QUICKSTART.md)
- [OPA Policy Development](03-policy-development.md)
- [User Validation](04-user-validation.md)
- [Security Overview](README.md)

## Support

For questions or issues:
- Check logs: `docker logs <container> | grep "A2A"`
- Test Guardian: `curl http://localhost:8383/health`
- Review policy: `curl http://localhost:8383/v1/policies`
- Email: jl.mrtz@gmail.com
