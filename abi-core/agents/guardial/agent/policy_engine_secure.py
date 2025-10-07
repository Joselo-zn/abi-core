import json
import logging
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

from opa.config import get_opa_config
from opa.policy_loader_v2 import get_policy_loader

logger = logging.getLogger(__name__)

class PolicyDecision(BaseModel):
    allow: bool
    deny: bool = False
    risk_score: float
    audit_log: Dict[str, Any]
    rules_evaluated: List[str] = []
    remediation_suggestions: List[str] = []

class SecurePolicyEngine:
    """
    Secure OPA Policy Engine for ABI Guardian Agent
    
    CRITICAL SECURITY FEATURES:
    - MANDATORY core policies - system won't start without them
    - Auto-generation of security policies at deployment
    - Fail-safe security defaults
    - Immutable core policy protection
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = get_opa_config(config_path)
        self.policy_loader = get_policy_loader(self.config.get('policies.base_path'))
        self.client = httpx.AsyncClient(timeout=self.config.get('opa.timeout', 30))
        self.policies_loaded = False
        self.security_validated = False
        
    async def initialize(self):
        """
        Initialize the policy engine with MANDATORY security validation
        
        CRITICAL: System will NOT start if core security policies are missing
        """
        try:
            logger.info("🔒 Initializing Secure Policy Engine...")
            
            # CRITICAL: Validate system security FIRST
            if not self.policy_loader.ensure_system_security():
                raise RuntimeError("CRITICAL SECURITY FAILURE: Core policies unavailable - SYSTEM BLOCKED")
            
            # Load all policies (including mandatory core policies)
            policies = self.policy_loader.load_all_policies()
            
            # CRITICAL: Validate that core policies are present
            validation_issues = self.policy_loader.validate_policies()
            critical_issues = [i for i in validation_issues if i.get('severity') == 'CRITICAL']
            
            if critical_issues:
                error_msg = f"CRITICAL SECURITY ISSUES: {len(critical_issues)} critical policy problems found"
                logger.error(f"🚨 {error_msg}")
                for issue in critical_issues:
                    logger.error(f"🚨 {issue['message']}")
                raise RuntimeError(error_msg)
            
            # Log non-critical issues
            other_issues = [i for i in validation_issues if i.get('severity') != 'CRITICAL']
            if other_issues:
                logger.warning(f"Policy validation found {len(other_issues)} non-critical issues")
                for issue in other_issues:
                    logger.warning(f"  {issue['policy']}: {issue['message']}")
            
            # Upload policies to OPA if configured
            if self.config.get('policies.auto_reload', True):
                await self._upload_policies_to_opa(policies)
            
            self.policies_loaded = True
            self.security_validated = True
            
            logger.info(f"✅ Secure Policy Engine initialized with {len(policies)} policies")
            logger.info("✅ SYSTEM SECURITY VALIDATED - Safe to operate")
            
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Failed to initialize secure policy engine: {e}")
            logger.error("🚨 SYSTEM STARTUP BLOCKED FOR SECURITY")
            if self.config.get('security.require_opa', True):
                raise RuntimeError(f"Security initialization failed: {e}")
    
    async def _upload_policies_to_opa(self, policies: Dict[str, str]):
        """Upload policies to OPA server using individual policy endpoints"""
        opa_url = self.config.get('opa.url')
        
        try:
            # Verify core policies are included
            core_policy_found = any('abi_policies' in name for name in policies.keys())
            if not core_policy_found:
                raise RuntimeError("CRITICAL: Core policies missing from upload")
            
            logger.info(f"📤 Uploading {len(policies)} policies to OPA at {opa_url}")
            
            # Upload each policy individually using the /v1/policies endpoint
            uploaded_count = 0
            for policy_name, policy_content in policies.items():
                try:
                    # Clean policy name for OPA (replace special characters)
                    clean_name = policy_name.replace('/', '_').replace('.', '_')
                    
                    # Debug logging for policy content
                    logger.info(f"🔍 Uploading policy '{clean_name}' with content length: {len(policy_content)}")
                    logger.debug(f"📄 Policy content preview (first 200 chars): {policy_content[:200]}...")
                    
                    # Upload policy to OPA
                    response = await self.client.put(
                        f"{opa_url}/v1/policies/{clean_name}",
                        data=policy_content,
                        headers={'Content-Type': 'text/plain'}
                    )
                    response.raise_for_status()
                    
                    uploaded_count += 1
                    logger.info(f"✅ Uploaded policy: {clean_name}")
                    
                except Exception as e:
                    logger.error(f"🚨 Failed to upload policy {policy_name}: {e}")
                    if 'abi_policies' in policy_name:  # Core policies are critical
                        raise RuntimeError(f"CRITICAL: Failed to upload core policy {policy_name}: {e}")
                    # Non-core policies can fail without blocking startup
                    logger.warning(f"⚠️ Continuing without policy {policy_name}")
            
            logger.info(f"✅ Successfully uploaded {uploaded_count}/{len(policies)} policies to OPA")
            
            if uploaded_count == 0:
                raise RuntimeError("CRITICAL: No policies were uploaded successfully")
            
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Failed to upload policies to OPA: {e}")
            if self.config.get('security.require_opa', True):
                raise RuntimeError(f"Policy upload failed: {e}")
    
    async def evaluate_policy(
        self, 
        action: str,
        resource_type: str,
        source_agent: str,
        target_agent: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        """
        Evaluate an action against ABI policies using OPA
        
        CRITICAL: Will fail-safe to DENY if security is not validated
        """
        
        # CRITICAL: Check security validation first
        if not self.security_validated:
            logger.error("🚨 CRITICAL: Security not validated - DENYING all actions")
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "Security not validated", "fail_safe": "deny"},
                remediation_suggestions=["System security validation required"]
            )
        
        if not self.policies_loaded:
            await self.initialize()
        
        # Prepare input for OPA
        policy_input = {
            "action": action,
            "resource_type": resource_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "content": content or "",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "security_context": {
                "policies_validated": self.security_validated,
                "core_policies_loaded": True
            }
        }
        
        try:
            # Query OPA for decision
            bundle_name = self.config.get('policies.bundle_name', 'abi')
            response = await self.client.post(
                f"{self.config.get('opa.url')}/v1/data/{bundle_name}",
                json={"input": policy_input}
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract results from both core and custom policies
            core_result = result.get("result", {}).get("core", {})
            custom_result = result.get("result", {}).get("custom", {})
            
            # Core policies have absolute veto power
            core_allow = core_result.get("allow", False)
            core_deny = core_result.get("deny", False)
            core_risk = core_result.get("risk_score", 1.0)
            
            # Custom policies can only be more restrictive
            custom_allow = custom_result.get("allow", True)
            custom_deny = custom_result.get("deny", False)
            custom_risk = custom_result.get("risk_score", 0.0)
            
            # Final decision: Core policies have veto power
            final_allow = core_allow and custom_allow and not core_deny and not custom_deny
            final_deny = core_deny or custom_deny or not core_allow
            final_risk = max(core_risk, custom_risk)
            
            # Apply risk score limits
            max_risk = self.config.get('security.max_risk_score', 1.0)
            if final_risk > max_risk:
                final_deny = True
                final_allow = False
            
            # Generate audit log
            audit_log = {
                "core_decision": {"allow": core_allow, "deny": core_deny, "risk": core_risk},
                "custom_decision": {"allow": custom_allow, "deny": custom_deny, "risk": custom_risk},
                "final_decision": {"allow": final_allow, "deny": final_deny, "risk": final_risk},
                "security_validated": self.security_validated,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Generate remediation suggestions if denied
            remediation = []
            if final_deny or not final_allow:
                remediation = await self._generate_remediation(policy_input, final_risk, core_deny)
            
            decision = PolicyDecision(
                allow=final_allow,
                deny=final_deny,
                risk_score=final_risk,
                audit_log=audit_log,
                rules_evaluated=["core_policies", "custom_policies"],
                remediation_suggestions=remediation
            )
            
            # Log the decision
            await self._log_decision(policy_input, decision)
            
            return decision
            
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to OPA: {e}")
            return await self._handle_opa_failure(policy_input)
            
        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
            return await self._handle_evaluation_error(policy_input, str(e))
    
    async def _handle_opa_failure(self, policy_input: Dict[str, Any]) -> PolicyDecision:
        """Handle OPA service failure with secure fail-safe"""
        fail_safe_mode = self.config.get('security.fail_safe_mode', 'deny')
        
        # CRITICAL: If security not validated, always deny
        if not self.security_validated:
            logger.error("🚨 CRITICAL: OPA failure + Security not validated = HARD DENY")
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "OPA unavailable + security not validated", "fail_safe": "hard_deny"},
                remediation_suggestions=["Validate system security", "Check OPA service availability"]
            )
        
        if fail_safe_mode == 'allow':
            logger.warning("⚠️ OPA unavailable - ALLOWING due to fail-safe mode (SECURITY RISK)")
            return PolicyDecision(
                allow=True,
                deny=False,
                risk_score=0.8,  # High risk due to no policy validation
                audit_log={"error": "OPA unavailable", "fail_safe": "allow", "security_risk": True},
                remediation_suggestions=["Check OPA service availability", "Review action manually"]
            )
        elif fail_safe_mode == 'warn':
            logger.warning("⚠️ OPA unavailable - ALLOWING with HIGH RISK warning")
            return PolicyDecision(
                allow=True,
                deny=False,
                risk_score=0.9,  # Very high risk
                audit_log={"error": "OPA unavailable", "fail_safe": "warn", "security_risk": True},
                remediation_suggestions=["Check OPA service availability", "Manual security review required"]
            )
        else:  # deny (default and most secure)
            logger.error("🚫 OPA unavailable - DENYING due to secure fail-safe mode")
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "OPA unavailable", "fail_safe": "deny"},
                remediation_suggestions=["Check OPA service availability"]
            )
    
    async def _generate_remediation(
        self, 
        policy_input: Dict[str, Any], 
        risk_score: float,
        core_denied: bool = False
    ) -> List[str]:
        """Generate remediation suggestions with security context"""
        
        suggestions = []
        
        if core_denied:
            suggestions.append("🚨 BLOCKED BY CORE SECURITY POLICY - Cannot be overridden")
            suggestions.append("Contact system administrator for security review")
        
        action = policy_input.get("action")
        resource_type = policy_input.get("resource_type")
        
        if action in ["create_agent", "spawn_process", "replicate"]:
            suggestions.append("🚫 Self-replication blocked by core security policy")
            suggestions.append("Agent creation requires human authorization")
        
        if action in ["write", "delete", "modify"] and resource_type in ["policy", "opa_config"]:
            suggestions.append("🚫 Policy modification blocked by core security")
            suggestions.append("Policy changes require administrative access")
        
        if action in ["write", "delete", "modify"]:
            suggestions.append("Consider using read-only operations instead")
            suggestions.append("Request explicit approval for write operations")
        
        if resource_type in ["system_config", "policy", "agent_core"]:
            suggestions.append("Critical resource access requires human approval")
            suggestions.append("Use staging environment for testing changes")
        
        if risk_score > 0.8:
            suggestions.append("High-risk operation detected - manual review required")
            suggestions.append("Consider breaking down into smaller, lower-risk operations")
        
        return suggestions
    
    async def _log_decision(
        self, 
        policy_input: Dict[str, Any], 
        decision: PolicyDecision
    ):
        """Log policy decision with security context"""
        
        if not self.config.get('logging.audit_enabled', True):
            return
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "security_validated": self.security_validated,
            "input": policy_input,
            "decision": {
                "allow": decision.allow,
                "deny": decision.deny,
                "risk_score": decision.risk_score
            },
            "rules_evaluated": decision.rules_evaluated,
            "remediation_provided": len(decision.remediation_suggestions) > 0,
            "audit_log": decision.audit_log
        }
        
        # Enhanced logging for security events
        if decision.deny and decision.risk_score > 0.8:
            logger.warning(f"🚫 HIGH-RISK ACTION BLOCKED: {json.dumps(audit_entry)}")
        elif self.config.get('logging.structured_logging', True):
            logger.info("POLICY_DECISION", extra={"audit": audit_entry})
        else:
            logger.info(f"Policy Decision: {json.dumps(audit_entry)}")
    
    async def _handle_evaluation_error(self, policy_input: Dict[str, Any], error: str) -> PolicyDecision:
        """Handle policy evaluation errors with security context"""
        return PolicyDecision(
            allow=False,
            deny=True,
            risk_score=1.0,
            audit_log={
                "error": error, 
                "timestamp": datetime.utcnow().isoformat(),
                "security_validated": self.security_validated
            },
            remediation_suggestions=["Review policy configuration", "Check input format", "Validate system security"]
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Enhanced health check with security validation"""
        
        health = {
            'policy_engine': 'healthy' if self.security_validated else 'SECURITY_NOT_VALIDATED',
            'policies_loaded': self.policies_loaded,
            'security_validated': self.security_validated,
            'opa_status': 'unknown',
            'config_valid': len(self.config.validate()) == 0,
            'core_policies_present': False
        }
        
        # Check for core policies with enhanced integrity information
        if self.policies_loaded:
            manifest = self.policy_loader.get_policy_manifest()
            health['core_policies_present'] = manifest.get('core_policies_loaded', False)
            
            # Add core policy integrity information
            core_generator = self.policy_loader.core_generator
            health['core_policy_integrity'] = {
                'checksums_count': len(core_generator.policy_checksums),
                'last_validation': core_generator.last_validation.isoformat() if core_generator.last_validation else None,
                'integrity_file_exists': (Path(self.policy_loader.base_policy_path) / core_generator.integrity_state_file).exists()
            }
        
        # Check OPA connectivity
        try:
            response = await self.client.get(f"{self.config.get('opa.url')}/health")
            health['opa_status'] = 'healthy' if response.status_code == 200 else 'unhealthy'
        except:
            health['opa_status'] = 'unreachable'
        
        # Overall system health
        health['system_secure'] = (
            health['security_validated'] and 
            health['core_policies_present'] and 
            health['opa_status'] == 'healthy'
        )
        
        return health
    
    async def reload_policies(self) -> bool:
        """
        Reload policies dynamically without restart
        
        Returns:
            True if reload successful, False otherwise
        """
        try:
            logger.info("🔄 Starting dynamic policy reload...")
            
            # Backup current state
            old_policies_loaded = self.policies_loaded
            old_security_validated = self.security_validated
            
            # Reset state for reload
            self.policies_loaded = False
            
            # Reload policies
            await self.initialize()
            
            if self.security_validated and self.policies_loaded:
                logger.info("✅ Dynamic policy reload successful")
                return True
            else:
                # Restore previous state on failure
                self.policies_loaded = old_policies_loaded
                self.security_validated = old_security_validated
                logger.error("🚨 Dynamic policy reload failed - restored previous state")
                return False
                
        except Exception as e:
            logger.error(f"🚨 Dynamic policy reload failed: {e}")
            # Restore previous state on exception
            self.policies_loaded = old_policies_loaded
            self.security_validated = old_security_validated
            return False
    
    async def validate_policy_changes(self) -> Dict[str, Any]:
        """
        Validate potential policy changes without applying them
        
        Returns:
            Validation results with issues and recommendations
        """
        try:
            # Create temporary policy loader for validation
            temp_loader = get_policy_loader(self.config.get('policies.base_path'))
            
            # Load policies for validation
            temp_policies = temp_loader.load_all_policies()
            
            # Validate policies
            validation_issues = temp_loader.validate_policies()
            
            # Check for critical issues
            critical_issues = [i for i in validation_issues if i.get('severity') == 'CRITICAL']
            
            return {
                'valid': len(critical_issues) == 0,
                'total_policies': len(temp_policies),
                'validation_issues': validation_issues,
                'critical_issues': critical_issues,
                'recommendations': self._generate_policy_recommendations(validation_issues)
            }
            
        except Exception as e:
            logger.error(f"Policy validation failed: {e}")
            return {
                'valid': False,
                'error': str(e),
                'recommendations': ['Fix policy loading errors before reload']
            }
    
    def _generate_policy_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on validation issues"""
        recommendations = []
        
        critical_count = len([i for i in issues if i.get('severity') == 'CRITICAL'])
        error_count = len([i for i in issues if i.get('severity') == 'ERROR'])
        warning_count = len([i for i in issues if i.get('severity') == 'WARNING'])
        
        if critical_count > 0:
            recommendations.append(f"Fix {critical_count} critical issues before reload")
        
        if error_count > 0:
            recommendations.append(f"Address {error_count} policy errors")
        
        if warning_count > 0:
            recommendations.append(f"Consider fixing {warning_count} policy warnings")
        
        if not issues:
            recommendations.append("Policies are valid and ready for reload")
        
        return recommendations
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Singleton instance
_secure_policy_engine = None

def get_secure_policy_engine(config_path: Optional[str] = None) -> SecurePolicyEngine:
    """Get singleton secure policy engine instance"""
    global _secure_policy_engine
    if _secure_policy_engine is None:
        _secure_policy_engine = SecurePolicyEngine(config_path)
    return _secure_policy_engine