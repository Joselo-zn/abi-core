# A2A Validation Quick Start

## 5-Minute Setup Guide

### Step 1: Verify Configuration

Check your agent's `config/config.py` has A2A variables:

```python
# config/config.py
class AgentConfig:
    # ... other config ...
    
    # A2A Validation
    A2A_VALIDATION_MODE: str = os.getenv('A2A_VALIDATION_MODE', 'strict')
    A2A_ENABLE_AUDIT_LOG: bool = os.getenv('A2A_ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    GUARDIAN_URL: str = os.getenv('GUARDIAN_URL', 'http://project-guardian:8383')
```

✅ **Already included** in all agents generated with `abi-core add agent`

### Step 2: Configure Environment

Add to your `compose.yaml`:

```yaml
services:
  my-orchestrator:
    environment:
      - A2A_VALIDATION_MODE=strict
      - A2A_ENABLE_AUDIT_LOG=true
      - GUARDIAN_URL=http://my-project-guardian:8383
```

### Step 3: Use in Orchestrator

```python
from config import config, AGENT_CARD
from abi_core.common.workflow import WorkflowGraph, WorkflowNode

# Create workflow
workflow = WorkflowGraph()

# Add nodes
node = WorkflowNode(task="Process data", agent_card=target_agent_card)
workflow.add_node(node)

# Set source card (IMPORTANT!)
workflow.set_source_card(AGENT_CARD)

# Run - validation happens automatically
async for chunk in workflow.run_workflow():
    process(chunk)
```

### Step 4: Configure OPA Policy

Edit `services/guardian/opa/policies/a2a_access.rego`:

```rego
communication_rules := [
    # Your orchestrator can talk to all agents
    {"source": "orchestrator", "target": "*", "bidirectional": false},
    
    # Specific agent pairs
    {"source": "data-agent", "target": "analytics-agent", "bidirectional": true},
]
```

### Step 5: Test

```bash
# Start your project
docker-compose up

# Check logs for A2A validation
docker logs my-project-orchestrator | grep "A2A Validator"

# You should see:
# [A2A Validator] Initialized with mode: strict
# [A2A Validator] ✅ Access granted: orchestrator -> data-agent
```

## Validation Modes

### Development
```bash
A2A_VALIDATION_MODE=permissive  # Allows on Guardian errors
```

### Production
```bash
A2A_VALIDATION_MODE=strict      # Denies on any error
```

### Testing
```bash
A2A_VALIDATION_MODE=disabled    # No validation (not recommended)
```

## Common Issues

### ❌ "source_card not provided"

**Solution**: Add `workflow.set_source_card(AGENT_CARD)` before running workflow

### ❌ "Guardian timeout"

**Solution**: 
1. Check Guardian is running: `docker ps | grep guardian`
2. Verify GUARDIAN_URL in config
3. Use `permissive` mode in development

### ❌ "Communication not allowed"

**Solution**: Add rule to `a2a_access.rego`:
```rego
{"source": "your-agent", "target": "target-agent", "bidirectional": false}
```

## Next Steps

- [Full A2A Documentation](06-a2a-validation.md)
- [OPA Policy Development](03-policy-development.md)
- [Security Best Practices](README.md)

## Need Help?

- Check logs: `docker logs <container> | grep "A2A"`
- Test Guardian: `curl http://localhost:8383/health`
- Verify policy: `curl http://localhost:8383/v1/policies`
