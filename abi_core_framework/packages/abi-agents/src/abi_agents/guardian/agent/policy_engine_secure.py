"""
Secure OPA Policy Engine for Guardian Agent.

CRITICAL SECURITY FEATURES:
- MANDATORY core policies — system won't start without them
- Auto-generation of security policies at deployment
- Fail-safe security defaults (deny on failure)
- Immutable core policy protection
"""

import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

from abi_core.opa.config import get_opa_config
from abi_core.opa.policy_loader_v2 import get_policy_loader

logger = logging.getLogger(__name__)


class PolicyDecision(BaseModel):
    allow: bool
    deny: bool = False
    risk_score: float
    audit_log: Dict[str, Any]
    rules_evaluated: List[str] = []
    remediation_suggestions: List[str] = []


class SecurePolicyEngine:
    """Secure OPA Policy Engine with mandatory security validation."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = get_opa_config(config_path)
        self.policy_loader = get_policy_loader(self.config.get("policies.base_path"))
        self.client = httpx.AsyncClient(timeout=self.config.get("opa.timeout", 30))
        self.policies_loaded = False
        self.security_validated = False

    async def initialize(self):
        """Initialize with MANDATORY security validation."""
        try:
            logger.info("🔒 Initializing Secure Policy Engine...")

            if not self.policy_loader.ensure_system_security():
                raise RuntimeError("CRITICAL: Core policies unavailable — SYSTEM BLOCKED")

            policies = self.policy_loader.load_all_policies()

            validation_issues = self.policy_loader.validate_policies()
            critical_issues = [i for i in validation_issues if i.get("severity") == "CRITICAL"]

            if critical_issues:
                for issue in critical_issues:
                    logger.error(f"🚨 {issue['message']}")
                raise RuntimeError(f"CRITICAL: {len(critical_issues)} policy problems found")

            if self.config.get("policies.auto_reload", True):
                await self._upload_policies_to_opa(policies)

            self.policies_loaded = True
            self.security_validated = True
            logger.info(f"✅ Policy Engine initialized with {len(policies)} policies")

        except Exception as e:
            logger.error(f"🚨 CRITICAL: Policy engine init failed: {e}")
            if self.config.get("security.require_opa", True):
                raise RuntimeError(f"Security initialization failed: {e}")

    async def _upload_policies_to_opa(self, policies: Dict[str, str]):
        """Upload policies to OPA server."""
        opa_url = self.config.get("opa.url")
        uploaded = 0

        for policy_name, policy_content in policies.items():
            try:
                clean_name = policy_name.replace("/", "_").replace(".", "_")
                response = await self.client.put(
                    f"{opa_url}/v1/policies/{clean_name}",
                    content=policy_content,
                    headers={"Content-Type": "text/plain"},
                )
                response.raise_for_status()
                uploaded += 1
            except Exception as e:
                if "abi_policies" in policy_name:
                    raise RuntimeError(f"CRITICAL: Failed to upload core policy {policy_name}: {e}")
                logger.warning(f"⚠️ Skipping policy {policy_name}: {e}")

        if uploaded == 0:
            raise RuntimeError("CRITICAL: No policies uploaded successfully")
        logger.info(f"✅ Uploaded {uploaded}/{len(policies)} policies to OPA")

    async def evaluate_policy(
        self,
        action: str,
        resource_type: str,
        source_agent: str,
        target_agent: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate action against OPA policies. Fail-safe: DENY."""

        if not self.security_validated:
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "Security not validated", "fail_safe": "deny"},
                remediation_suggestions=["System security validation required"],
            )

        if not self.policies_loaded:
            await self.initialize()

        policy_input = {
            "action": action,
            "resource_type": resource_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "content": content or "",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        try:
            bundle_name = self.config.get("policies.bundle_name", "abi")
            response = await self.client.post(
                f"{self.config.get('opa.url')}/v1/data/{bundle_name}",
                json={"input": policy_input},
            )
            response.raise_for_status()
            result = response.json()

            core_result = result.get("result", {}).get("core", {})
            custom_result = result.get("result", {}).get("custom", {})

            core_allow = core_result.get("allow", False)
            core_deny = core_result.get("deny", False)
            core_risk = core_result.get("risk_score", 1.0)

            custom_allow = custom_result.get("allow", True)
            custom_deny = custom_result.get("deny", False)
            custom_risk = custom_result.get("risk_score", 0.0)

            final_allow = core_allow and custom_allow and not core_deny and not custom_deny
            final_deny = core_deny or custom_deny or not core_allow
            final_risk = max(core_risk, custom_risk)

            remediation = []
            if final_deny:
                remediation = self._generate_remediation(action, resource_type, core_deny)

            return PolicyDecision(
                allow=final_allow,
                deny=final_deny,
                risk_score=final_risk,
                audit_log={
                    "core": {"allow": core_allow, "deny": core_deny, "risk": core_risk},
                    "custom": {"allow": custom_allow, "deny": custom_deny, "risk": custom_risk},
                    "timestamp": datetime.utcnow().isoformat(),
                },
                rules_evaluated=["core_policies", "custom_policies"],
                remediation_suggestions=remediation,
            )

        except httpx.RequestError:
            return self._fail_safe_decision("OPA unavailable")
        except Exception as e:
            return self._fail_safe_decision(str(e))

    def _fail_safe_decision(self, error: str) -> PolicyDecision:
        """Fail-safe: deny on any error."""
        return PolicyDecision(
            allow=False,
            deny=True,
            risk_score=1.0,
            audit_log={"error": error, "fail_safe": "deny"},
            remediation_suggestions=["Check OPA service availability"],
        )

    def _generate_remediation(self, action: str, resource_type: str, core_denied: bool) -> List[str]:
        suggestions = []
        if core_denied:
            suggestions.append("🚨 BLOCKED BY CORE SECURITY POLICY — cannot be overridden")
        if action in ("create_agent", "spawn_process", "replicate"):
            suggestions.append("Agent creation requires human authorization")
        if resource_type in ("policy", "opa_config", "agent_core"):
            suggestions.append("Critical resource access requires admin approval")
        return suggestions

    async def health_check(self) -> Dict[str, Any]:
        """Health check with security validation."""
        health = {
            "policies_loaded": self.policies_loaded,
            "security_validated": self.security_validated,
            "opa_status": "unknown",
            "core_policies_present": False,
        }

        if self.policies_loaded:
            manifest = self.policy_loader.get_policy_manifest()
            health["core_policies_present"] = manifest.get("core_policies_loaded", False)

        try:
            response = await self.client.get(f"{self.config.get('opa.url')}/health")
            health["opa_status"] = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            health["opa_status"] = "unreachable"

        health["system_secure"] = (
            health["security_validated"]
            and health["core_policies_present"]
            and health["opa_status"] == "healthy"
        )
        return health

    async def close(self):
        await self.client.aclose()


# Singleton
_engine: Optional[SecurePolicyEngine] = None


def get_secure_policy_engine(config_path: Optional[str] = None) -> SecurePolicyEngine:
    global _engine
    if _engine is None:
        _engine = SecurePolicyEngine(config_path)
    return _engine
