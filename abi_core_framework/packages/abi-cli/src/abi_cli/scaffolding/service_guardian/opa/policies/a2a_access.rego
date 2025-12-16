package a2a_access

import future.keywords.if
import future.keywords.in

# ============================================
# A2A ACCESS CONTROL POLICY
# ============================================
# Controls agent-to-agent communication
# Validates if source agent can communicate with target agent

# Default deny
default allow := false

# ============================================
# VALIDATION MODE
# ============================================

validation_mode := input.validation_mode

# Disabled mode - always allow
allow if {
    validation_mode == "disabled"
}

# ============================================
# AGENT VALIDATION
# ============================================

# Extract agent information
source_agent := input.source_agent
target_agent := input.target_agent

# Validate agent names exist
agents_identified if {
    source_agent.name != ""
    source_agent.name != "unknown"
    target_agent.name != ""
    target_agent.name != "unknown"
}

# ============================================
# BLOCKED COMMUNICATIONS (Optional)
# ============================================
# Use this to explicitly block specific communications
# even if they would be allowed by the rules below.
# Uncomment and add pairs to block:

# blocked_communications := [
#     {"source": "Abi Orchestrator Agent", "target": "Planner Agent"},
#     {"source": "Planner Agent", "target": "Abi Orchestrator Agent"},
# ]

# Check if communication is explicitly blocked
# is_blocked_communication if {
#     some i
#     blocked_communications[i].source == source_agent.name
#     blocked_communications[i].target == target_agent.name
# }

# ============================================
# COMMUNICATION RULES
# ============================================

communication_rules := [
    # Orchestrator can talk to everyone
    {"source": "Abi Orchestrator Agent", "target": "*", "bidirectional": false},
    
    # Planner can talk to orchestrator
    {"source": "Planner Agent", "target": "Abi Orchestrator Agent", "bidirectional": true},
    
    # Semantic layer can be accessed by all agents
    {"source": "*", "target": "semantic-layer", "bidirectional": false},
    
    # Example: specific agent pairs (use full agent card names)
    # {"source": "Data Agent", "target": "Analytics Agent", "bidirectional": true},
    # {"source": "UI Agent", "target": "Abi Orchestrator Agent", "bidirectional": false},
]

# Check if allowed by rules
is_allowed_communication if {
    some i
    communication_rules[i].source == source_agent.name
    communication_rules[i].target == target_agent.name
}

is_allowed_communication if {
    some i
    communication_rules[i].source == target_agent.name
    communication_rules[i].target == source_agent.name
    communication_rules[i].bidirectional == true
}

is_allowed_communication if {
    some i
    communication_rules[i].source == source_agent.name
    communication_rules[i].target == "*"
}

is_allowed_communication if {
    some i
    communication_rules[i].source == "*"
    communication_rules[i].target == target_agent.name
}

# ============================================
# MAIN ALLOW RULE
# ============================================
# NOTE: If you enable blocked_communications above,
# you MUST uncomment the "not is_blocked_communication" line below
# or the block list will be ignored!

allow if {
    agents_identified
    is_allowed_communication
    # not is_blocked_communication  # ← UNCOMMENT THIS if using blocked_communications
}

# ============================================
# DENY REASONS
# ============================================

deny_reason := reason if {
    not agents_identified
    reason := "Source or target agent not properly identified"
}

# Uncomment this if using blocked_communications:
# deny_reason := reason if {
#     agents_identified
#     is_blocked_communication
#     reason := sprintf(
#         "Communication explicitly blocked: %s -> %s",
#         [source_agent.name, target_agent.name]
#     )
# }

deny_reason := reason if {
    agents_identified
    # not is_blocked_communication  # ← UNCOMMENT THIS if using blocked_communications
    not is_allowed_communication
    reason := sprintf(
        "Communication not allowed: %s -> %s",
        [source_agent.name, target_agent.name]
    )
}

# ============================================
# AUDIT INFORMATION
# ============================================

audit_info := {
    "source_agent": source_agent.name,
    "target_agent": target_agent.name,
    "timestamp": input.communication.timestamp,
    "message_length": input.communication.message_length,
    "allowed": allow,
    "reason": deny_reason,
    "validation_mode": validation_mode
}
