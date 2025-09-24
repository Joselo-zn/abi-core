# Example Custom Policies for ABI
# This file demonstrates how users can extend ABI policies

package abi.custom

import rego.v1

# Custom rule: Block operations during maintenance window
deny if {
    input.action in ["write", "delete", "execute"]
    is_maintenance_window
}

# Custom rule: Allow specific agents to access development resources
allow if {
    input.action == "read"
    input.resource_type == "dev_resource"
    input.source_agent in dev_agents
}

# Custom rule: Require approval for high-value operations
require_approval if {
    input.action in ["delete", "modify"]
    input.resource_type in ["production_data", "user_accounts"]
    input.metadata.estimated_impact == "high"
}

# Helper functions
is_maintenance_window if {
    # Check if current time is within maintenance window
    # This would typically check against a schedule
    hour := time.clock(time.now_ns())[0]
    hour >= 2
    hour <= 4
}

dev_agents := {
    "dev_orchestrator",
    "test_agent",
    "staging_actor"
}

# Custom risk scoring
custom_risk_score := score if {
    base_risk := 0.1
    
    # Increase risk during off-hours
    hour := time.clock(time.now_ns())[0]
    time_multiplier := 1.5 if hour < 8 or hour > 18 else 1.0
    
    # Increase risk for sensitive operations
    action_multiplier := 2.0 if input.action in ["delete", "modify"] else 1.0
    
    score := base_risk * time_multiplier * action_multiplier
}