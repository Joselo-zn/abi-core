"""
A2A Access Validator
Validates agent-to-agent communication using OPA policies via Guardian
"""

import os
import logging
import httpx
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)


class A2AAccessValidator:
    """Validates A2A communication access using OPA policies"""
    
    def __init__(
        self,
        guardian_url: Optional[str] = None,
        opa_url: Optional[str] = None,
        validation_mode: str = "strict",
        enable_audit_log: bool = True
    ):
        """
        Initialize A2A Access Validator
        
        Args:
            guardian_url: Guardian service URL (for audit logs)
            opa_url: OPA service URL (for policy evaluation, default: from env OPA_URL)
            validation_mode: Validation mode - strict/permissive/disabled
            enable_audit_log: Enable audit logging
        """
        self.guardian_url = guardian_url or os.getenv(
            "GUARDIAN_URL", 
            "http://localhost:11438"
        )
        # OPA URL for policy evaluation (separate from Guardian)
        self.opa_url = opa_url or os.getenv(
            "OPA_URL",
            "http://localhost:8181"
        )
        self.validation_mode = validation_mode
        self.enable_audit_log = enable_audit_log
        
        logger.info(f"[A2A Validator] Initialized with mode: {validation_mode}")
        logger.info(f"[A2A Validator] OPA URL: {self.opa_url}")
        logger.info(f"[A2A Validator] Guardian URL: {self.guardian_url}")
        logger.info(f"[A2A Validator] Audit logging: {enable_audit_log}")

    def build_a2a_context(
        self,
        source_agent_card: Any,
        target_agent_card: Any,
        message: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build context for A2A access validation
        
        Args:
            source_agent_card: Source agent card (AgentCard object or dict)
            target_agent_card: Target agent card (AgentCard object or dict)
            message: Message being sent (for logging)
            additional_context: Additional metadata
            
        Returns:
            Context dictionary for OPA evaluation
        """
        # Extract source agent info
        if hasattr(source_agent_card, 'model_dump'):
            source_info = source_agent_card.model_dump()
        elif hasattr(source_agent_card, 'dict'):
            source_info = source_agent_card.dict()
        elif isinstance(source_agent_card, dict):
            source_info = source_agent_card
        else:
            source_info = {"name": str(source_agent_card)}
        
        # Extract target agent info
        if hasattr(target_agent_card, 'model_dump'):
            target_info = target_agent_card.model_dump()
        elif hasattr(target_agent_card, 'dict'):
            target_info = target_agent_card.dict()
        elif isinstance(target_agent_card, dict):
            target_info = target_agent_card
        else:
            target_info = {"name": str(target_agent_card)}
        
        # Build context
        context = {
            "source_agent": {
                "name": source_info.get("name", "unknown"),
                "description": source_info.get("description", ""),
                "capabilities": source_info.get("capabilities", []),
                "url": source_info.get("url", ""),
            },
            "target_agent": {
                "name": target_info.get("name", "unknown"),
                "description": target_info.get("description", ""),
                "capabilities": target_info.get("capabilities", []),
                "url": target_info.get("url", ""),
            },
            "communication": {
                "timestamp": datetime.utcnow().isoformat(),
                "message_preview": message[:100] if message else None,
                "message_length": len(message) if message else 0,
            },
            "validation_mode": self.validation_mode,
        }
        
        # Add additional context if provided
        if additional_context:
            context["metadata"] = additional_context
        
        return context

    async def validate_a2a_access(
        self,
        source_agent_card: Any,
        target_agent_card: Any,
        message: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate A2A communication access
        
        Args:
            source_agent_card: Source agent card
            target_agent_card: Target agent card
            message: Message being sent
            additional_context: Additional metadata
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Disabled mode - always allow
        if self.validation_mode == "disabled":
            logger.debug("[A2A Validator] Validation disabled - allowing access")
            return True, None
        
        # Build context
        context = self.build_a2a_context(
            source_agent_card=source_agent_card,
            target_agent_card=target_agent_card,
            message=message,
            additional_context=additional_context
        )
        
        # Log validation attempt
        logger.info(
            f"[A2A Validator] Validating: {context['source_agent']['name']} -> "
            f"{context['target_agent']['name']}"
        )
        
        try:
            # Call OPA to evaluate policy
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.opa_url}/v1/data/a2a_access/allow",
                    json={"input": context}
                )
                
                if response.status_code != 200:
                    error_msg = f"Guardian returned status {response.status_code}"
                    logger.error(f"[A2A Validator] {error_msg}")
                    
                    # Permissive mode - allow on error
                    if self.validation_mode == "permissive":
                        logger.warning("[A2A Validator] Permissive mode - allowing despite error")
                        return True, None
                    
                    return False, error_msg
                
                result = response.json()
                is_allowed = result.get("result", False)
                
                # Get denial reason if not allowed
                reason = None
                if not is_allowed:
                    # Try to get detailed reason from policy
                    reason_response = await client.post(
                        f"{self.opa_url}/v1/data/a2a_access/deny_reason",
                        json={"input": context}
                    )
                    if reason_response.status_code == 200:
                        reason_data = reason_response.json()
                        reason = reason_data.get("result", "Access denied by policy")
                    else:
                        reason = "Access denied by policy"
                
                # Audit log
                if self.enable_audit_log:
                    await self._audit_log(context, is_allowed, reason)
                
                if is_allowed:
                    logger.info(
                        f"[A2A Validator] ✅ Access granted: "
                        f"{context['source_agent']['name']} -> {context['target_agent']['name']}"
                    )
                else:
                    logger.warning(
                        f"[A2A Validator] ❌ Access denied: "
                        f"{context['source_agent']['name']} -> {context['target_agent']['name']} "
                        f"Reason: {reason}"
                    )
                
                return is_allowed, reason
                
        except httpx.TimeoutException:
            logger.error("[A2A Validator] Guardian request timeout")
            
            # Permissive mode - allow on timeout
            if self.validation_mode == "permissive":
                logger.warning("[A2A Validator] Permissive mode - allowing despite timeout")
                return True, None
            
            return False, "Guardian timeout"
            
        except Exception as e:
            logger.error(f"[A2A Validator] Error validating access: {e}")
            
            # Permissive mode - allow on error
            if self.validation_mode == "permissive":
                logger.warning("[A2A Validator] Permissive mode - allowing despite error")
                return True, None
            
            return False, f"Validation error: {str(e)}"

    async def _audit_log(
        self,
        context: Dict[str, Any],
        is_allowed: bool,
        reason: Optional[str]
    ):
        """Send audit log to Guardian"""
        try:
            audit_data = {
                "event_type": "a2a_access",
                "timestamp": context["communication"]["timestamp"],
                "source_agent": context["source_agent"]["name"],
                "target_agent": context["target_agent"]["name"],
                "allowed": is_allowed,
                "reason": reason,
                "context": context
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.guardian_url}/audit/log",
                    json=audit_data
                )
        except Exception as e:
            logger.warning(f"[A2A Validator] Failed to send audit log: {e}")


# Global validator instance
_validator_instance = None


def get_validator() -> A2AAccessValidator:
    """Get or create global validator instance"""
    global _validator_instance
    if _validator_instance is None:
        # Try to import config first, fallback to env vars
        try:
            from config import config
            validation_mode = config.A2A_VALIDATION_MODE
            enable_audit = config.A2A_ENABLE_AUDIT_LOG
            guardian_url = config.GUARDIAN_URL
            opa_url = getattr(config, 'OPA_URL', None)
        except (ImportError, AttributeError):
            # Fallback to environment variables
            validation_mode = os.getenv("A2A_VALIDATION_MODE", "strict")
            enable_audit = os.getenv("A2A_ENABLE_AUDIT_LOG", "true").lower() == "true"
            guardian_url = os.getenv("GUARDIAN_URL", "http://localhost:11438")
            opa_url = os.getenv("OPA_URL", "http://localhost:8181")
        
        _validator_instance = A2AAccessValidator(
            guardian_url=guardian_url,
            opa_url=opa_url,
            validation_mode=validation_mode,
            enable_audit_log=enable_audit
        )
    
    return _validator_instance


def validate_a2a_access(a2a: Tuple[Any, Any], **decorator_kwargs):
    """
    Decorator to validate A2A communication access
    
    Usage:
        @validate_a2a_access(a2a=(SOURCE_CARD, TARGET_CARD))
        async def send_message(message: str):
            # communication logic
            pass
    
    Args:
        a2a: Tuple of (source_agent_card, target_agent_card)
        **decorator_kwargs: Additional context to pass to validator
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            source_card, target_card = a2a
            
            # Extract message from kwargs if present
            message = kwargs.get("message") or kwargs.get("query") or kwargs.get("prompt")
            
            # Get validator
            validator = get_validator()
            
            # Validate access
            is_allowed, reason = await validator.validate_a2a_access(
                source_agent_card=source_card,
                target_agent_card=target_card,
                message=message,
                additional_context=decorator_kwargs
            )
            
            if not is_allowed:
                raise PermissionError(
                    f"A2A communication denied: {source_card.name if hasattr(source_card, 'name') else 'unknown'} -> "
                    f"{target_card.name if hasattr(target_card, 'name') else 'unknown'}. "
                    f"Reason: {reason}"
                )
            
            # Execute original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
