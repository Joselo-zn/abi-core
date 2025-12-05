# A2A Access Validation

## Overview

The A2A (Agent-to-Agent) Access Validator controls communication between agents in your ABI system. It uses OPA policies via Guardian to enforce rules about which agents can communicate with each other.

## Key Features

- **Policy-based control**: Define communication rules in OPA
- **Decorator pattern**: Easy integration with `@validate_a2a_access`
- **Multiple modes**: strict, permissive, or disabled validation
- **Audit logging**: Track all communication attempts
- **Metadata support**: Include context in validation decisions

## Architecture

```
Agent A → A2A Validator → Guardian → OPA Policy → Allow/Deny
                ↓
          Audit Log
```

## Configuration

### Using config.py (Recommended)

All A2A validation settings are centralized in your agent's `config/config.py`:

```python
from config import config

# Access A2A configuration
print(config.A2A_VALIDATION_MODE)      # strict, permissive, or disabled
print(config.A2A_ENABLE_AUDIT_LOG)     # True or False
print(config.GUARDIAN_URL)              # Guardian service URL
```

The validator automatically reads from `config.py` when available.

### Environment Variables

You can configure A2A validation through environment variables (loaded into config.py):

```bash
# Validation mode: strict, permissive, or disabled
A2A_VALIDATION_MODE=permissive

# Enable audit logging
A2A_ENABLE_AUDIT_LOG=true

# OPA service URL for policy evaluation (uses project name automatically)
OPA_URL=http://my-project-opa:8181

# Guardian service URL for audit logs (uses project name automatically)
GUARDIAN_URL=http://my-project-guardian:11438
```

**Important:** 
- `OPA_URL` is used for policy evaluation (port 8181)
- `GUARDIAN_URL` is used for audit logging (port 11438)
- Both URLs use Docker service names in containerized environments

### Validation Modes

1. **strict**: Deny access on any error or policy violation
2. **permissive**: Allow access if Guardian is unavailable, deny only on explicit policy violation
3. **disabled**: Allow all communication (bypass validation)

## Usage

### Automatic Validation (Recommended)

The easiest way to use A2A validation is through the `agent_connection()` function, which automatically validates all agent-to-agent communications:

```python
from abi_core.common.abi_a2a import agent_connection
from config import AGENT_CARD  # Your agent's card

# Load target agent card
target_card = load_agent_card("path/to/target/agent_card.json")

# Prepare payload
payload = {
    'message': {
        'role': 'user',
        'parts': [{'kind': 'text', 'text': 'Hello from orchestrator'}],
        'messageId': 'task-123',
        'contextId': 'ctx-456'
    }
}

# Connect with automatic validation
try:
    async for chunk in agent_connection(AGENT_CARD, target_card, payload):
        print(chunk)
except PermissionError as e:
    print(f"A2A communication denied: {e}")
```

### Using with WorkflowGraph

```python
from abi_core.common.workflow import WorkflowGraph, WorkflowNode
from config import AGENT_CARD

# Create workflow
workflow = WorkflowGraph()

# Add nodes with target agents
node1 = WorkflowNode(task="Process data", agent_card=data_agent_card)
workflow.add_node(node1)

# Set source card for A2A validation (important!)
workflow.set_source_card(AGENT_CARD)

# Run workflow - validation happens automatically
async for chunk in workflow.run_workflow():
    print(chunk)
```

### Basic Decorator Usage (Manual)

For custom functions, you can use the decorator directly:

```python
from abi_core.security.a2a_access_validator import validate_a2a_access
from config import AGENT_CARD

# Load target agent card
target_card = load_agent_card("path/to/target/agent_card.json")

@validate_a2a_access(a2a=(AGENT_CARD, target_card))
async def send_message_to_agent(message: str):
    """This function only executes if validation passes"""
    response = await http_client.post(
        target_card.url + "/send_message",
        json={"message": message}
    )
    return response.json()

# Usage
try:
    result = await send_message_to_agent("Hello!")
    print(result)
except PermissionError as e:
    print(f"Access denied: {e}")
```

### Manual Validation

```python
from abi_core.security.a2a_access_validator import get_validator

validator = get_validator()

is_allowed, reason = await validator.validate_a2a_access(
    source_agent_card=source_card,
    target_agent_card=target_card,
    message="Test message",
    additional_context={"priority": "high"}
)

if is_allowed:
    # Proceed with communication
    pass
else:
    print(f"Denied: {reason}")
```

### Custom Validator

```python
from abi_core.security.a2a_access_validator import A2AAccessValidator

validator = A2AAccessValidator(
    guardian_url="http://custom-guardian:8383",
    validation_mode="permissive",
    enable_audit_log=True
)

is_allowed, reason = await validator.validate_a2a_access(
    source_agent_card=source_card,
    target_agent_card=target_card
)
```

## OPA Policy

### Policy Location

```
services/guardian/opa/policies/a2a_access.rego
```

### Default Rules

The default policy includes:

1. **Orchestrator** can communicate with all agents
2. **Planner** can communicate bidirectionally with orchestrator
3. **All agents** can access semantic layer
4. Custom rules can be added

### Policy Structure

```rego
package a2a_access

# Default deny
default allow := false

# Allow orchestrator to talk to everyone
allow if {
    input.source_agent.name == "orchestrator"
}

# Allow specific pairs
allow if {
    some rule in communication_rules
    rule.source == input.source_agent.name
    rule.target == input.target_agent.name
}

# Communication rules database
communication_rules := [
    {"source": "orchestrator", "target": "*", "bidirectional": false},
    {"source": "planner", "target": "orchestrator", "bidirectional": true},
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
]
```

### Adding Custom Rules

Edit the `communication_rules` array in `a2a_access.rego`:

```rego
communication_rules := [
    # Your custom rules
    {"source": "data-agent", "target": "analytics-agent", "bidirectional": true},
    {"source": "ui-agent", "target": "orchestrator", "bidirectional": false},
    
    # Wildcard rules
    {"source": "admin-agent", "target": "*", "bidirectional": false},
    {"source": "*", "target": "public-api", "bidirectional": false},
]
```

### Blocking Specific Communications

There are three approaches to block specific agent-to-agent communications:

#### Option 1: Remove Permissive Rules (Recommended)

The simplest approach is to use a whitelist model - only allow what you explicitly permit:

```rego
communication_rules := [
    # Only allow specific communications
    {"source": "orchestrator", "target": "data-agent", "bidirectional": false},
    {"source": "orchestrator", "target": "analytics-agent", "bidirectional": false},
    # Note: orchestrator -> planner is NOT listed, so it's blocked
    
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
]
```

**Example: Block Orchestrator → Planner**

Remove the wildcard rule and only allow specific targets:

```rego
communication_rules := [
    # OLD (allows everything):
    # {"source": "orchestrator", "target": "*", "bidirectional": false},
    
    # NEW (explicit whitelist):
    {"source": "orchestrator", "target": "data-agent", "bidirectional": false},
    {"source": "orchestrator", "target": "analytics-agent", "bidirectional": false},
    # planner is not in the list, so communication is blocked
    
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
]
```

#### Option 2: Explicit Blocklist

Add a blocklist for specific communications that should never be allowed:

```rego
# ============================================
# BLOCKED COMMUNICATIONS
# ============================================

blocked_communications := [
    {"source": "orchestrator", "target": "planner"},
    {"source": "planner", "target": "orchestrator"},
    {"source": "untrusted-agent", "target": "sensitive-data-agent"},
]

# Check if communication is explicitly blocked
is_blocked_communication if {
    some rule in blocked_communications
    rule.source == source_agent.name
    rule.target == target_agent.name
}

# Update the main allow rule to check for blocks
allow if {
    agents_identified
    is_allowed_communication
    not is_blocked_communication  # ← Add this condition
}
```

**Complete example with blocklist:**

```rego
package a2a_access

import future.keywords.if
import future.keywords.in

default allow := false

source_agent := input.source_agent
target_agent := input.target_agent

# Blocked communications (highest priority)
blocked_communications := [
    {"source": "orchestrator", "target": "planner"},
    {"source": "planner", "target": "orchestrator"},
]

is_blocked_communication if {
    some rule in blocked_communications
    rule.source == source_agent.name
    rule.target == target_agent.name
}

# Allowed communications
communication_rules := [
    {"source": "orchestrator", "target": "*", "bidirectional": false},
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
]

is_allowed_communication if {
    some rule in communication_rules
    rule.source == source_agent.name
    rule.target == target_agent.name
}

# Main allow rule - checks both allow and block lists
allow if {
    source_agent.name != ""
    target_agent.name != ""
    is_allowed_communication
    not is_blocked_communication  # Block takes precedence
}
```

#### Option 3: Conditional Rules

Block communications based on conditions like time, message content, or metadata:

```rego
# Block during maintenance window
is_maintenance_window if {
    # Check if current time is in maintenance window
    time.now_ns() > maintenance_start
    time.now_ns() < maintenance_end
}

# Block high-risk communications
is_high_risk_communication if {
    source_agent.name == "external-agent"
    target_agent.name == "database-agent"
}

# Deny if conditions are met
allow if {
    agents_identified
    is_allowed_communication
    not is_blocked_communication
    not is_maintenance_window
    not is_high_risk_communication
}
```

### Testing Your Policy

After modifying the policy, test it using OPA's evaluation endpoint:

```bash
# Test if orchestrator can talk to planner
curl -X POST http://localhost:8181/v1/data/a2a_access/allow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "source_agent": {"name": "orchestrator"},
      "target_agent": {"name": "planner"},
      "validation_mode": "strict"
    }
  }'

# Expected response for blocked communication:
# {"result": false}
```

### Policy Reload

After updating the policy file, Guardian automatically reloads it (if `AUTO_RELOAD_POLICIES=true`). You can also manually reload:

```bash
# Check policy status
curl http://localhost:8383/v1/policies

# Force reload (if endpoint available)
curl -X POST http://localhost:8383/v1/policies/reload
```

## Context Structure

The validator builds a context object sent to OPA:

```json
{
  "source_agent": {
    "name": "orchestrator",
    "description": "Main orchestrator agent",
    "capabilities": ["planning", "coordination"],
    "url": "http://orchestrator:8001"
  },
  "target_agent": {
    "name": "data-agent",
    "description": "Data processing agent",
    "capabilities": ["data_processing"],
    "url": "http://data-agent:8002"
  },
  "communication": {
    "timestamp": "2024-12-02T10:30:00Z",
    "message_preview": "Process this data...",
    "message_length": 150
  },
  "validation_mode": "strict",
  "metadata": {
    "priority": "high",
    "task_id": "task-123"
  }
}
```

## Audit Logging

When enabled, all validation attempts are logged to Guardian:

```json
{
  "event_type": "a2a_access",
  "timestamp": "2024-12-02T10:30:00Z",
  "source_agent": "orchestrator",
  "target_agent": "data-agent",
  "allowed": true,
  "reason": null,
  "context": { ... }
}
```

## Error Handling

### Permission Denied

```python
try:
    await send_message_to_agent("Hello")
except PermissionError as e:
    # Handle denial
    logger.warning(f"Communication denied: {e}")
    # Maybe retry, notify user, or use alternative agent
```

### Guardian Unavailable

In **strict** mode, communication is denied if Guardian is unavailable.
In **permissive** mode, communication is allowed if Guardian is unavailable.

```python
# Strict mode
A2A_VALIDATION_MODE=strict  # Deny on Guardian error

# Permissive mode
A2A_VALIDATION_MODE=permissive  # Allow on Guardian error
```

## Best Practices

1. **Use strict mode in production** for maximum security
2. **Use permissive mode in development** for easier debugging
3. **Always include meaningful context** in additional_context
4. **Monitor audit logs** to detect unauthorized access attempts
5. **Keep policies simple** - complex rules are harder to debug
6. **Test policies** before deploying to production

## Integration with Orchestrator

### Automatic Integration (Built-in)

A2A validation is automatically integrated in the workflow system. When you use `WorkflowGraph`, validation happens transparently:

```python
from abi_core.common.workflow import WorkflowGraph, WorkflowNode
from config import AGENT_CARD

class Orchestrator:
    def __init__(self):
        self.agent_card = AGENT_CARD
    
    async def execute_workflow(self, plan):
        # Create workflow from plan
        workflow = WorkflowGraph()
        
        for task in plan.tasks:
            node = WorkflowNode(
                task=task.description,
                agent_card=task.agent_card
            )
            workflow.add_node(node)
        
        # Set orchestrator as source for A2A validation
        workflow.set_source_card(self.a

## Troubleshooting

### Validation Always Fails

1. Check OPA is running: `curl http://localhost:8181/health`
2. Check policy is loaded: `curl http://localhost:8181/v1/policies`
3. Check validation mode: `echo $A2A_VALIDATION_MODE`
4. Check OPA_URL is correct: `echo $OPA_URL`
5. Check logs for detailed error messages

### 404 Error from Guardian

If you see "Guardian returned status 404":
- The validator is trying to call Guardian instead of OPA
- Check that `OPA_URL` is set correctly
- OPA should be at port 8181, not Guardian's port 11438
- Restart services after updating environment variables

### Validation Always Passes

1. Check if mode is `disabled`: `echo $A2A_VALIDATION_MODE`
2. Check if wildcard rules are too permissive
3. Review policy logic in `a2a_access.rego`

### OPA/Guardian Timeout

1. Increase timeout in validator initialization
2. Check OPA performance and resources
3. Check Guardian performance for audit logs
4. Consider using permissive mode if OPA is unstable
5. Verify network connectivity between containers

## Related Documentation

- [OPA Policies](02-opa-policies.md)
- [User Validation](04-user-validation.md)
- [Agent Cards](../user-guide/agent-cards.md)
- [Guardian Service](../reference/architecture.md#guardian)
