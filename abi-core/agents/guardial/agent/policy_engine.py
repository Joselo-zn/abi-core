import json
import logging
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PolicyDecision(BaseModel):
    allow: bool
    deny: bool = False
    risk_score: float
    audit_log: Dict[str, Any]
    rules_evaluated: List[str] = []
    remediation_suggestions: List[str] = []

class PolicyEngine:
    """OPA Policy Engine for ABI Guardian Agent"""
    
    def __init__(self, opa_url: str = "http://opa:8181"):
        self.opa_url = opa_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
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
        
        Args:
            action: The action being performed (read, write, execute, etc.)
            resource_type: Type of resource being accessed
            source_agent: Agent requesting the action
            target_agent: Target agent (for communication)
            content: Content being processed (for sensitive data detection)
            metadata: Additional context
            
        Returns:
            PolicyDecision with allow/deny and risk assessment
        """
        
        # Prepare input for OPA
        policy_input = {
            "action": action,
            "resource_type": resource_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "content": content or "",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        try:
            # Query OPA for decision
            response = await self.client.post(
                f"{self.opa_url}/v1/data/abi/policies",
                json={"input": policy_input}
            )
            response.raise_for_status()
            
            result = response.json()
            opa_result = result.get("result", {})
            
            # Extract decision components
            allow = opa_result.get("allow", False)
            deny = opa_result.get("deny", False)
            risk_score = opa_result.get("risk_score", 1.0)
            audit_log = opa_result.get("audit_log", {})
            rules_evaluated = opa_result.get("rules_evaluated", [])
            
            # Generate remediation suggestions if denied
            remediation = []
            if deny or not allow:
                remediation = await self._generate_remediation(
                    policy_input, risk_score
                )
            
            decision = PolicyDecision(
                allow=allow and not deny,
                deny=deny,
                risk_score=risk_score,
                audit_log=audit_log,
                rules_evaluated=rules_evaluated,
                remediation_suggestions=remediation
            )
            
            # Log the decision
            await self._log_decision(policy_input, decision)
            
            return decision
            
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to OPA: {e}")
            # Fail-safe: deny by default if OPA is unreachable
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "OPA unreachable", "timestamp": datetime.utcnow().isoformat()},
                remediation_suggestions=["Check OPA service availability"]
            )
        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": str(e), "timestamp": datetime.utcnow().isoformat()},
                remediation_suggestions=["Review policy configuration"]
            )
    
    async def _generate_remediation(
        self, 
        policy_input: Dict[str, Any], 
        risk_score: float
    ) -> List[str]:
        """Generate remediation suggestions based on policy violation"""
        
        suggestions = []
        action = policy_input.get("action")
        resource_type = policy_input.get("resource_type")
        
        if action in ["write", "delete", "modify"]:
            suggestions.append("Consider using read-only operations instead")
            suggestions.append("Request explicit approval for write operations")
        
        if resource_type in ["system_config", "policy", "agent_core"]:
            suggestions.append("Critical resource access requires human approval")
            suggestions.append("Use staging environment for testing changes")
        
        if risk_score > 0.8:
            suggestions.append("High-risk operation detected - manual review required")
            suggestions.append("Consider breaking down into smaller, lower-risk operations")
        
        if policy_input.get("content") and "api" in policy_input["content"].lower():
            suggestions.append("Potential API key detected - review content for sensitive data")
        
        return suggestions
    
    async def _log_decision(
        self, 
        policy_input: Dict[str, Any], 
        decision: PolicyDecision
    ):
        """Log policy decision for audit trail"""
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "input": policy_input,
            "decision": {
                "allow": decision.allow,
                "deny": decision.deny,
                "risk_score": decision.risk_score
            },
            "rules_evaluated": decision.rules_evaluated,
            "remediation_provided": len(decision.remediation_suggestions) > 0
        }
        
        # Log to structured logger (could be sent to audit system)
        logger.info(f"Policy Decision: {json.dumps(audit_entry)}")
    
    async def health_check(self) -> bool:
        """Check if OPA service is healthy"""
        try:
            response = await self.client.get(f"{self.opa_url}/health")
            return response.status_code == 200
        except:
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Singleton instance
_policy_engine = None

def get_policy_engine() -> PolicyEngine:
    """Get singleton policy engine instance"""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine