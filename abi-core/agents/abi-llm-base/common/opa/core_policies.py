"""
ABI Core Policies Generator

This module contains the essential security policies for ABI.
These policies are generated at runtime and are REQUIRED for system operation.
The system will NOT start without these core policies.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class CorePolicyGenerator:
    """
    Generates and validates core ABI security policies
    
    These policies are MANDATORY and cannot be overridden.
    The system will fail to start if these policies are missing or invalid.
    """
    
    CORE_POLICY_TEMPLATE = '''# ABI Core Security Policies
# Generated at: {timestamp}
# Version: {version}
# WARNING: This file is auto-generated. DO NOT EDIT MANUALLY.
# System will NOT function without these core policies.

package abi.core

import rego.v1

# =============================================================================
# CRITICAL SECURITY POLICIES - CANNOT BE OVERRIDDEN
# =============================================================================

# Default deny - EVERYTHING must be explicitly allowed
default allow := false
default deny := false
default risk_score := 1.0

# =============================================================================
# FUNDAMENTAL SECURITY RULES
# =============================================================================

# CRITICAL: Block all self-replication attempts
deny if {{
    input.action in ["create_agent", "spawn_process", "replicate", "fork", "clone"]
    reason := "CRITICAL_VIOLATION: Self-replication blocked"
}}

# CRITICAL: Block policy modification by agents
deny if {{
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config", "security_config"]
    input.source_agent != "human_operator"
    reason := "CRITICAL_VIOLATION: Policy modification blocked"
}}

# CRITICAL: Block system-level access
deny if {{
    input.action in ["execute", "shell", "system"]
    input.resource_type in ["system", "os", "kernel", "root"]
    reason := "CRITICAL_VIOLATION: System access blocked"
}}

# CRITICAL: Block network access to unauthorized endpoints
deny if {{
    input.action == "network_request"
    not input.destination in allowed_endpoints
    reason := "CRITICAL_VIOLATION: Unauthorized network access"
}}

# CRITICAL: Block access to sensitive system files
deny if {{
    input.action in ["read", "write", "delete"]
    input.resource_type in ["system_config", "credentials", "keys", "certificates"]
    input.source_agent != "authorized_system_agent"
    reason := "CRITICAL_VIOLATION: Sensitive file access blocked"
}}

# =============================================================================
# AGENT COMMUNICATION RULES
# =============================================================================

# Allow communication between valid agents only
allow if {{
    input.action == "agent_communication"
    input.source_agent in valid_agents
    input.target_agent in valid_agents
    not contains_sensitive_data(input.content)
    not contains_malicious_patterns(input.content)
}}

# =============================================================================
# RESOURCE ACCESS RULES
# =============================================================================

# Allow read operations with risk assessment
allow if {{
    input.action == "read"
    input.resource_type in safe_read_resources
    calculated_risk_score < 0.5
    not contains_sensitive_data(input.content)
}}

# Allow low-risk write operations
allow if {{
    input.action == "write"
    input.resource_type in ["temp_file", "log", "cache"]
    calculated_risk_score < 0.3
    not contains_sensitive_data(input.content)
}}

# =============================================================================
# RISK SCORING SYSTEM
# =============================================================================

calculated_risk_score := score if {{
    base_score := action_risk_scores[input.action]
    resource_multiplier := resource_risk_multipliers[input.resource_type]
    context_modifier := context_risk_modifier
    sensitive_data_penalty := sensitive_data_risk_penalty
    
    score := base_score * resource_multiplier * context_modifier + sensitive_data_penalty
}}

# Action risk base scores
action_risk_scores := {{
    "read": 0.1,
    "write": 0.4,
    "delete": 0.8,
    "execute": 0.7,
    "modify": 0.6,
    "network_request": 0.5,
    "agent_communication": 0.2,
    "create_agent": 1.0,
    "spawn_process": 1.0,
    "system": 1.0
}}

# Resource risk multipliers
resource_risk_multipliers := {{
    "document": 1.0,
    "temp_file": 0.8,
    "log": 0.6,
    "cache": 0.7,
    "config": 1.5,
    "agent_card": 1.2,
    "system_config": 3.0,
    "policy": 3.0,
    "credentials": 3.0,
    "keys": 3.0,
    "certificates": 3.0,
    "system": 3.0
}}

# Context-based risk modification
context_risk_modifier := modifier if {{
    hour := time.clock(time.now_ns())[0]
    
    # Higher risk during off-hours
    off_hours_multiplier := 1.3 if (hour < 8 or hour > 18) else 1.0
    
    # Higher risk for emergency operations
    emergency_multiplier := 1.5 if input.metadata.emergency else 1.0
    
    # Higher risk for external requests
    external_multiplier := 1.4 if input.metadata.external_source else 1.0
    
    modifier := off_hours_multiplier * emergency_multiplier * external_multiplier
}}

# Sensitive data risk penalty
sensitive_data_risk_penalty := penalty if {{
    penalty := 0.5 if contains_sensitive_data(input.content) else 0.0
}}

# =============================================================================
# SECURITY DETECTION FUNCTIONS
# =============================================================================

# Detect sensitive data patterns
contains_sensitive_data(content) if {{
    # Social Security Numbers
    regex.match(`\\b\\d{{3}}-\\d{{2}}-\\d{{4}}\\b`, content)
}}

contains_sensitive_data(content) if {{
    # API Keys and tokens
    regex.match(`(?i)(api[_-]?key|token|secret|password)[\"\\s]*[:=][\"\\s]*[a-zA-Z0-9]{{20,}}`, content)
}}

contains_sensitive_data(content) if {{
    # Credit card numbers
    regex.match(`\\b\\d{{4}}[\\s-]?\\d{{4}}[\\s-]?\\d{{4}}[\\s-]?\\d{{4}}\\b`, content)
}}

contains_sensitive_data(content) if {{
    # Email addresses (potential PII)
    regex.match(`\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{{2,}}\\b`, content)
}}

# Detect malicious patterns
contains_malicious_patterns(content) if {{
    # Command injection patterns
    regex.match(`(?i)(rm\\s+-rf|del\\s+/|format\\s+c:|shutdown|reboot)`, content)
}}

contains_malicious_patterns(content) if {{
    # SQL injection patterns
    regex.match(`(?i)(drop\\s+table|delete\\s+from|truncate|alter\\s+table)`, content)
}}

contains_malicious_patterns(content) if {{
    # Script injection patterns
    regex.match(`(?i)(<script|javascript:|eval\\(|exec\\()`, content)
}}

# =============================================================================
# SYSTEM CONFIGURATION
# =============================================================================

# Valid agents that can communicate
valid_agents := {{
    "orchestrator",
    "planner",
    "actor", 
    "observer",
    "guardial",
    "semantic_layer"
}}

# Safe resources for read operations
safe_read_resources := {{
    "document",
    "agent_card",
    "public_config",
    "log",
    "cache",
    "temp_file"
}}

# Allowed network endpoints
allowed_endpoints := {{
    "localhost",
    "127.0.0.1",
    "abi-llm-base",
    "abi-weaviate", 
    "semantic-layer",
    "abi-orchestrator",
    "abi-planner",
    "abi-actor",
    "abi-observer"
}}

# =============================================================================
# AUDIT AND COMPLIANCE
# =============================================================================

# Generate audit log for every decision
audit_log := {{
    "timestamp": time.now_ns(),
    "decision": {{
        "allow": allow,
        "deny": deny,
        "risk_score": calculated_risk_score
    }},
    "input": input,
    "policy_version": "{version}",
    "core_policies": true,
    "rules_evaluated": rules_evaluated,
    "security_violations": security_violations
}}

# Track which rules were evaluated
rules_evaluated := [rule |
    rule := "core_self_replication_block"
    input.action in ["create_agent", "spawn_process", "replicate"]
]

rules_evaluated := [rule |
    rule := "core_policy_protection"
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config"]
]

rules_evaluated := [rule |
    rule := "core_system_protection"
    input.action in ["execute", "shell", "system"]
]

# Track security violations
security_violations := [violation |
    violation := {{
        "type": "self_replication_attempt",
        "severity": "CRITICAL",
        "action": input.action
    }}
    input.action in ["create_agent", "spawn_process", "replicate"]
]

security_violations := [violation |
    violation := {{
        "type": "policy_modification_attempt", 
        "severity": "CRITICAL",
        "resource": input.resource_type
    }}
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config"]
]

security_violations := [violation |
    violation := {{
        "type": "sensitive_data_exposure",
        "severity": "HIGH", 
        "content_length": count(input.content)
    }}
    contains_sensitive_data(input.content)
]
'''

    def __init__(self):
        self.version = "1.0.0"
        self.required_policies = ["abi.core"]
        
    def generate_core_policies(self) -> str:
        """
        Generate the core ABI security policies
        
        Returns:
            Complete Rego policy content
        """
        timestamp = datetime.utcnow().isoformat()
        
        return self.CORE_POLICY_TEMPLATE.format(
            timestamp=timestamp,
            version=self.version
        )
    
    def write_core_policies(self, output_path: str) -> bool:
        """
        Write core policies to file
        
        Args:
            output_path: Path where to write the policies
            
        Returns:
            True if successful, False otherwise
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            policy_content = self.generate_core_policies()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(policy_content)
            
            logger.info(f"Core policies generated successfully: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate core policies: {e}")
            return False
    
    def validate_core_policies_exist(self, policy_path: str) -> bool:
        """
        Validate that core policies exist and are valid
        
        Args:
            policy_path: Path to check for core policies
            
        Returns:
            True if core policies exist and are valid
        """
        core_policy_file = Path(policy_path) / "abi_policies.rego"
        
        if not core_policy_file.exists():
            logger.error(f"CRITICAL: Core policies not found at {core_policy_file}")
            return False
        
        try:
            with open(core_policy_file, 'r') as f:
                content = f.read()
            
            # Check for required policy elements
            required_elements = [
                "package abi.core",
                "default allow := false",
                "create_agent",
                "spawn_process", 
                "replicate"
            ]
            
            for element in required_elements:
                if element not in content:
                    logger.error(f"CRITICAL: Core policy missing required element: {element}")
                    return False
            
            logger.info("Core policies validation passed")
            return True
            
        except Exception as e:
            logger.error(f"CRITICAL: Failed to validate core policies: {e}")
            return False
    
    def ensure_core_policies(self, policy_directory: str) -> bool:
        """
        Ensure core policies exist, generate if missing
        
        Args:
            policy_directory: Directory where policies should exist
            
        Returns:
            True if core policies are available, False if system should not start
        """
        policy_file = Path(policy_directory) / "abi_policies.rego"
        
        # Check if policies exist and are valid
        if self.validate_core_policies_exist(policy_directory):
            return True
        
        # Generate core policies
        logger.warning("Core policies missing, generating...")
        success = self.write_core_policies(str(policy_file))
        
        if not success:
            logger.error("CRITICAL: Failed to generate core policies - SYSTEM CANNOT START")
            return False
        
        # Validate generated policies
        if not self.validate_core_policies_exist(policy_directory):
            logger.error("CRITICAL: Generated core policies are invalid - SYSTEM CANNOT START")
            return False
        
        return True

# Singleton instance
_core_policy_generator = None

def get_core_policy_generator() -> CorePolicyGenerator:
    """Get singleton core policy generator"""
    global _core_policy_generator
    if _core_policy_generator is None:
        _core_policy_generator = CorePolicyGenerator()
    return _core_policy_generator