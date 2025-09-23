package abi.policies

import rego.v1

# Default deny - everything must be explicitly allowed
default allow := false

# Default risk score
default risk_score := 0.0

# Allow basic agent communication
allow if {
    input.action == "agent_communication"
    input.source_agent in valid_agents
    input.target_agent in valid_agents
    not contains_sensitive_data
}

# Allow read operations with low risk
allow if {
    input.action == "read"
    input.resource_type in ["document", "config", "agent_card"]
    risk_score < 0.3
}

# Block write operations to critical resources
deny if {
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["system_config", "policy", "agent_core"]
}

# Block external network access
deny if {
    input.action == "network_request"
    not input.destination in allowed_endpoints
}

# Block self-replication attempts
deny if {
    input.action in ["create_agent", "spawn_process", "replicate"]
}

# Calculate risk score based on multiple factors
risk_score := score if {
    base_score := action_risk[input.action]
    resource_multiplier := resource_risk[input.resource_type]
    context_modifier := context_risk
    score := base_score * resource_multiplier * context_modifier
}

# Action risk mapping
action_risk := {
    "read": 0.1,
    "write": 0.5,
    "delete": 0.8,
    "execute": 0.6,
    "network_request": 0.7,
    "agent_communication": 0.2,
    "create_agent": 1.0,
    "modify_policy": 1.0
}

# Resource risk mapping
resource_risk := {
    "document": 1.0,
    "config": 1.5,
    "agent_card": 1.2,
    "system_config": 2.0,
    "policy": 2.5,
    "agent_core": 3.0,
    "external_api": 1.8
}

# Context risk based on time, user, etc.
context_risk := modifier if {
    # Higher risk during off-hours
    hour := time.clock(time.now_ns())[0]
    off_hours := hour < 8 or hour > 18
    
    # Higher risk for sensitive operations
    sensitive_operation := input.action in ["delete", "modify_policy", "create_agent"]
    
    modifier := 1.0
    modifier := 1.3 if off_hours
    modifier := 1.5 if sensitive_operation
    modifier := 2.0 if off_hours and sensitive_operation
}

# Valid agents that can communicate
valid_agents := {
    "orchestrator",
    "planner", 
    "actor",
    "observer",
    "guardial"
}

# Allowed external endpoints
allowed_endpoints := {
    "localhost",
    "127.0.0.1",
    "abi-llm-base",
    "abi-weaviate",
    "semantic-layer"
}

# Check for sensitive data patterns
contains_sensitive_data if {
    # Check for PII patterns
    regex.match(`\b\d{3}-\d{2}-\d{4}\b`, input.content)  # SSN
}

contains_sensitive_data if {
    # Check for API keys
    regex.match(`(?i)(api[_-]?key|token|secret)["\s]*[:=]["\s]*[a-zA-Z0-9]{20,}`, input.content)
}

contains_sensitive_data if {
    # Check for credit card numbers
    regex.match(`\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b`, input.content)
}

# Audit log structure
audit_log := {
    "timestamp": time.now_ns(),
    "decision": allow,
    "risk_score": risk_score,
    "input": input,
    "policy_version": "1.0.0",
    "rules_evaluated": rules_evaluated
}

# Track which rules were evaluated
rules_evaluated := [rule |
    rule := sprintf("allow_%s", [input.action])
    allow
]