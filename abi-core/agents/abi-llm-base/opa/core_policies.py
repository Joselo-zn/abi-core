"""
ABI Core Policies Generator

This module contains the essential security policies for ABI.
These policies are generated at runtime and are REQUIRED for system operation.
The system will NOT start without these core policies.
"""

import os
import logging
import hashlib
import json
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

# =============================================================================
# CRITICAL SECURITY POLICIES - CANNOT BE OVERRIDDEN
# =============================================================================

# Default deny - EVERYTHING must be explicitly allowed
default allow := false
default risk_score := 1.0

# =============================================================================
# SYSTEM CONFIGURATION (must be defined first)
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

# =============================================================================
# SECURITY DETECTION FUNCTIONS
# =============================================================================

# Detect sensitive data patterns - SSN
contains_sensitive_data(content) if {{
    regex.match(`\\b\\d{{3}}-\\d{{2}}-\\d{{4}}\\b`, content)
}}

# Detect sensitive data patterns - API Keys
contains_sensitive_data(content) if {{
    regex.match(`(?i)(api[_-]?key|token|secret|password)["\\s]*[:=]["\\s]*[a-zA-Z0-9]{{20,}}`, content)
}}

# Detect sensitive data patterns - Credit Cards
contains_sensitive_data(content) if {{
    regex.match(`\\b\\d{{4}}[\\s-]?\\d{{4}}[\\s-]?\\d{{4}}[\\s-]?\\d{{4}}\\b`, content)
}}

# Detect sensitive data patterns - Emails
contains_sensitive_data(content) if {{
    regex.match(`\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{{2,}}\\b`, content)
}}

# Detect malicious patterns - Commands
contains_malicious_patterns(content) if {{
    regex.match(`(?i)(rm\\s+-rf|del\\s+/|format\\s+c:|shutdown|reboot)`, content)
}}

# Detect malicious patterns - SQL
contains_malicious_patterns(content) if {{
    regex.match(`(?i)(drop\\s+table|delete\\s+from|truncate|alter\\s+table)`, content)
}}

# Detect malicious patterns - Scripts
contains_malicious_patterns(content) if {{
    regex.match(`(?i)(<script|javascript:|eval\\(|exec\\()`, content)
}}

# =============================================================================
# FUNDAMENTAL SECURITY RULES - DENY RULES
# =============================================================================

# CRITICAL: Block all self-replication attempts
deny contains "CRITICAL_VIOLATION: Self-replication blocked" if {{
    input.action in ["create_agent", "spawn_process", "replicate", "fork", "clone"]
}}

# CRITICAL: Block policy modification by agents
deny contains "CRITICAL_VIOLATION: Policy modification blocked" if {{
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config", "security_config"]
    input.source_agent != "human_operator"
}}

# CRITICAL: Block system-level access
deny contains "CRITICAL_VIOLATION: System access blocked" if {{
    input.action in ["execute", "shell", "system"]
    input.resource_type in ["system", "os", "kernel", "root"]
}}

# CRITICAL: Block network access to unauthorized endpoints
deny contains "CRITICAL_VIOLATION: Unauthorized network access" if {{
    input.action == "network_request"
    not input.destination in allowed_endpoints
}}

# CRITICAL: Block access to sensitive system files
deny contains "CRITICAL_VIOLATION: Sensitive file access blocked" if {{
    input.action in ["read", "write", "delete"]
    input.resource_type in ["system_config", "credentials", "keys", "certificates"]
    input.source_agent != "authorized_system_agent"
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

# Calculate base action risk
base_action_risk = score if {{
    score := action_risk_scores[input.action]
}}

base_action_risk = 1.0 if {{
    not action_risk_scores[input.action]
}}

# Calculate resource multiplier
resource_multiplier = mult if {{
    mult := resource_risk_multipliers[input.resource_type]
}}

resource_multiplier = 1.0 if {{
    not resource_risk_multipliers[input.resource_type]
}}

# Calculate off-hours multiplier
off_hours_multiplier = 1.3 if {{
    hour := time.clock(time.now_ns())[0]
    hour < 8
}}

off_hours_multiplier = 1.3 if {{
    hour := time.clock(time.now_ns())[0]
    hour > 18
}}

off_hours_multiplier = 1.0 if {{
    hour := time.clock(time.now_ns())[0]
    hour >= 8
    hour <= 18
}}

# Emergency multiplier
emergency_multiplier = 1.5 if {{
    input.metadata.emergency == true
}}

emergency_multiplier = 1.0 if {{
    not input.metadata.emergency
}}

emergency_multiplier = 1.0 if {{
    not input.metadata
}}

# External source multiplier
external_multiplier = 1.4 if {{
    input.metadata.external_source == true
}}

external_multiplier = 1.0 if {{
    not input.metadata.external_source
}}

external_multiplier = 1.0 if {{
    not input.metadata
}}

# Sensitive data penalty
sensitive_data_penalty = 0.5 if {{
    input.content
    contains_sensitive_data(input.content)
}}

sensitive_data_penalty = 0.0 if {{
    input.content
    not contains_sensitive_data(input.content)
}}

sensitive_data_penalty = 0.0 if {{
    not input.content
}}

# Calculate final risk score
calculated_risk_score = score if {{
    base := base_action_risk
    resource := resource_multiplier
    off_hours := off_hours_multiplier
    emergency := emergency_multiplier
    external := external_multiplier
    sensitive := sensitive_data_penalty
    
    score := (base * resource * off_hours * emergency * external) + sensitive
}}

# =============================================================================
# AUDIT AND COMPLIANCE
# =============================================================================

# Track evaluated rules
evaluated_rules contains rule if {{
    input.action in ["create_agent", "spawn_process", "replicate", "fork", "clone"]
    rule := "core_self_replication_block"
}}

evaluated_rules contains rule if {{
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config", "security_config"]
    rule := "core_policy_protection"
}}

evaluated_rules contains rule if {{
    input.action in ["execute", "shell", "system"]
    input.resource_type in ["system", "os", "kernel", "root"]
    rule := "core_system_protection"
}}

evaluated_rules contains rule if {{
    input.action == "network_request"
    rule := "core_network_protection"
}}

evaluated_rules contains rule if {{
    input.action in ["read", "write", "delete"]
    input.resource_type in ["system_config", "credentials", "keys", "certificates"]
    rule := "core_sensitive_file_protection"
}}

# Security violations tracking
security_violations contains violation if {{
    input.action in ["create_agent", "spawn_process", "replicate", "fork", "clone"]
    violation := {{
        "type": "self_replication_attempt",
        "severity": "CRITICAL",
        "action": input.action,
        "timestamp": time.now_ns()
    }}
}}

security_violations contains violation if {{
    input.action in ["write", "delete", "modify"]
    input.resource_type in ["policy", "opa_config", "security_config"]
    violation := {{
        "type": "policy_modification_attempt",
        "severity": "CRITICAL",
        "resource": input.resource_type,
        "timestamp": time.now_ns()
    }}
}}

security_violations contains violation if {{
    input.content
    contains_sensitive_data(input.content)
    violation := {{
        "type": "sensitive_data_exposure",
        "severity": "HIGH",
        "timestamp": time.now_ns()
    }}
}}

security_violations contains violation if {{
    input.content
    contains_malicious_patterns(input.content)
    violation := {{
        "type": "malicious_pattern_detected",
        "severity": "HIGH",
        "timestamp": time.now_ns()
    }}
}}

# Audit log generation
audit_log = {{
    "timestamp": time.now_ns(),
    "decision": {{
        "allow": allow,
        "deny": count(deny) > 0,
        "deny_reasons": [r | deny[r]],
        "risk_score": calculated_risk_score
    }},
    "input": input,
    "policy_version": "{version}",
    "evaluated_rules": [r | evaluated_rules[r]],
    "security_violations": [v | security_violations[v]]
}}
'''

    def __init__(self):
        self.version = "1.0.0"
        self.required_policies = ["abi.core"]
        self.policy_checksums = {}
        self.last_validation = None
        self.integrity_state_file = ".abi_policy_integrity.json"
        
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
            logger.info(f"📝 Writing core policies to: {output_path}")
            output_file = Path(output_path)
            
            # Ensure parent directory exists
            logger.info(f"📁 Ensuring parent directory exists: {output_file.parent}")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate policy content
            logger.info("🔧 Generating core policy content...")
            policy_content = self.generate_core_policies()
            logger.info(f"📊 Generated policy content length: {len(policy_content)} characters")
            
            # Write to file
            logger.info(f"💾 Writing to file: {output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(policy_content)
            
            # Verify file was written
            if output_file.exists():
                file_size = output_file.stat().st_size
                logger.info(f"✅ Core policies written successfully: {output_path} ({file_size} bytes)")
                return True
            else:
                logger.error(f"🚨 File was not created: {output_path}")
                return False
            
        except Exception as e:
            logger.error(f"🚨 Failed to generate core policies: {e}")
            import traceback
            logger.error(f"🚨 Traceback: {traceback.format_exc()}")
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
                    logger.error(f"CRITICAL: Core policy missing required element: {content}")
                    return False
            
            logger.info("Core policies validation passed")
            return True
            
        except Exception as e:
            logger.error(f"CRITICAL: Failed to validate core policies: {e}")
            return False
    
    def ensure_core_policies(self, policy_directory: str) -> bool:
        """
        Ensure core policies exist, generate if missing, regenerate if corrupted
        
        Args:
            policy_directory: Directory where policies should exist
            
        Returns:
            True if core policies are available, False if system should not start
        """
        logger.info(f"🔐 Ensuring core policies in directory: {policy_directory}")
        policy_file = Path(policy_directory) / "abi_policies.rego"
        logger.info(f"🔍 Looking for core policy file: {policy_file}")
        
        # Load existing integrity state
        logger.info("📋 Loading existing integrity state...")
        self.load_integrity_state(policy_directory)
        
        # Check if policies exist
        if not policy_file.exists():
            logger.warning("⚠️ Core policies missing, generating...")
            success = self.write_core_policies(str(policy_file))
            
            if not success:
                logger.error("🚨 CRITICAL: Failed to generate core policies - SYSTEM CANNOT START")
                return False
            logger.info("✅ Core policies generated successfully")
        else:
            logger.info("📄 Core policy file exists, validating...")
        
        # Validate policy integrity
        logger.info("🔍 Validating policy integrity...")
        if not self.validate_policy_integrity(str(policy_file)):
            logger.error("🚨 CRITICAL: Core policy integrity validation failed")
            
            # Attempt automatic regeneration
            logger.warning("🔄 Attempting automatic policy regeneration...")
            if not self.regenerate_corrupted_policies(policy_directory):
                logger.error("🚨 CRITICAL: Failed to regenerate corrupted policies - SYSTEM CANNOT START")
                return False
            
            logger.info("✅ Core policies successfully regenerated after corruption detection")
        else:
            logger.info("✅ Policy integrity validation passed")
        
        # Final validation check
        logger.info("🔍 Performing final policy validation...")
        if not self.validate_core_policies_exist(policy_directory):
            logger.error("🚨 CRITICAL: Final policy validation failed - SYSTEM CANNOT START")
            return False
        
        # Save integrity state
        logger.info("💾 Saving integrity state...")
        self.save_integrity_state(policy_directory)
        
        logger.info("✅ Core policies validated and integrity confirmed")
        return True
    
    def calculate_policy_checksum(self, policy_content: str) -> str:
        """Calculate SHA-256 checksum of policy content"""
        return hashlib.sha256(policy_content.encode('utf-8')).hexdigest()
    
    def save_integrity_state(self, policy_directory: str) -> bool:
        """Save policy integrity state to file"""
        try:
            state_file = Path(policy_directory) / self.integrity_state_file
            state = {
                'version': self.version,
                'checksums': self.policy_checksums,
                'last_validation': self.last_validation.isoformat() if self.last_validation else None,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Policy integrity state saved: {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save integrity state: {e}")
            return False
    
    def load_integrity_state(self, policy_directory: str) -> bool:
        """Load policy integrity state from file"""
        try:
            state_file = Path(policy_directory) / self.integrity_state_file
            
            if not state_file.exists():
                logger.info("No existing integrity state found")
                return False
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.policy_checksums = state.get('checksums', {})
            last_val = state.get('last_validation')
            self.last_validation = datetime.fromisoformat(last_val) if last_val else None
            
            logger.info(f"Policy integrity state loaded: {len(self.policy_checksums)} checksums")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load integrity state: {e}")
            return False
    
    def validate_policy_integrity(self, policy_path: str) -> bool:
        """Validate policy integrity using checksums and required elements"""
        try:
            policy_file = Path(policy_path)
            
            if not policy_file.exists():
                logger.error(f"Policy file not found: {policy_file}")
                return False
            
            # Read current policy content
            with open(policy_file, 'r') as f:
                current_content = f.read()
            
            # Calculate current checksum
            current_checksum = self.calculate_policy_checksum(current_content)
            
            # Check if we have a stored checksum
            policy_name = policy_file.name
            stored_checksum = self.policy_checksums.get(policy_name)
            
            if stored_checksum and stored_checksum != current_checksum:
                logger.error(f"Policy integrity violation detected: {policy_name}")
                logger.error(f"Expected: {stored_checksum}, Got: {current_checksum}")
                return False
            
            # Validate required elements
            required_elements = [
                "package abi.core",
                "default allow := false",
                "create_agent",
                "spawn_process", 
                "replicate"
            ]
            
            for element in required_elements:
                if element not in current_content:
                    logger.error(f"Policy missing required element: {element}")
                    return False
            
            # Update checksum and validation time
            self.policy_checksums[policy_name] = current_checksum
            self.last_validation = datetime.utcnow()
            
            logger.info(f"Policy integrity validation passed: {policy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Policy integrity validation failed: {e}")
            return False
    
    def regenerate_corrupted_policies(self, policy_directory: str) -> bool:
        """Regenerate policies when corruption is detected"""
        try:
            logger.warning("Regenerating corrupted core policies...")
            
            # Generate new policies
            policy_file = Path(policy_directory) / "abi_policies.rego"
            success = self.write_core_policies(str(policy_file))
            
            if not success:
                logger.error("Failed to regenerate core policies")
                return False
            
            # Validate regenerated policies
            if not self.validate_policy_integrity(str(policy_file)):
                logger.error("Regenerated policies failed validation")
                return False
            
            # Save new integrity state
            self.save_integrity_state(policy_directory)
            
            logger.info("Core policies successfully regenerated")
            return True
            
        except Exception as e:
            logger.error(f"Policy regeneration failed: {e}")
            return False

# Singleton instance
_core_policy_generator = None

def get_core_policy_generator() -> CorePolicyGenerator:
    """Get singleton core policy generator"""
    global _core_policy_generator
    if _core_policy_generator is None:
        _core_policy_generator = CorePolicyGenerator()
    return _core_policy_generator
