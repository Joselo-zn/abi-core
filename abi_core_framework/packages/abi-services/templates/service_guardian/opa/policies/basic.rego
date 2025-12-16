# Basic ABI OPA Policies
package abi.basic

import rego.v1

# Default deny - everything must be explicitly allowed
default allow := false
default deny := false
default risk_score := 1.0

# Basic allow rule for health checks
allow if {
    input.action == "health_check"
}

# Basic allow rule for low-risk read operations
allow if {
    input.action == "read"
    input.resource_type in ["public_document", "log", "status"]
    not contains_sensitive_data(input.content)
}

# Risk scoring
risk_score := score if {
    base_score := action_risk_scores[input.action]
    score := base_score
}

# Action risk base scores
action_risk_scores := {
    "read": 0.1,
    "write": 0.5,
    "delete": 0.8,
    "execute": 0.9,
    "health_check": 0.0
}

# Helper function to detect sensitive data
contains_sensitive_data(content) if {
    # Simple check for now
    regex.match(`(?i)(password|secret|key|token)`, content)
}

# Audit log
audit_log := {
    "timestamp": time.now_ns(),
    "decision": {
        "allow": allow,
        "deny": deny,
        "risk_score": risk_score
    },
    "input": input,
    "policy": "basic"
}