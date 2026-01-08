"""
Decorador para validación de acceso semántico usando políticas OPA con quotas
"""

import os
import json
import asyncio
import httpx
import hmac
import hashlib
import base64
from functools import wraps, lru_cache
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from abi_core.common.utils import abi_logging
from abi_core.security.agent_auth import sign_payload_hmac

# Configuration - will be overridden by config module if available
try:
    from config import config as semantic_config
    GUARDIAN_URL = semantic_config.GUARDIAN_URL
    OPA_URL = semantic_config.OPA_URL
    AGENT_CARD_DIR = Path(semantic_config.AGENT_CARDS_BASE)
    REQUIRE_USER_VALIDATION = semantic_config.REQUIRE_USER_VALIDATION
    REQUIRE_AGENT_VALIDATION = semantic_config.REQUIRE_AGENT_VALIDATION
    VALIDATION_MODE = semantic_config.VALIDATION_MODE
    ENABLE_QUOTA_MANAGEMENT = semantic_config.ENABLE_QUOTA_MANAGEMENT
    SEMANTIC_LAYER_DAILY_QUOTA = semantic_config.SEMANTIC_LAYER_DAILY_QUOTA
except ImportError:
    # Fallback to environment variables
    GUARDIAN_URL = os.getenv("GUARDIAN_URL", "")
    OPA_URL = os.getenv("OPA_URL", "")
    AGENT_CARD_DIR = Path(os.getenv("AGENT_CARDS_BASE", "/app/agent_cards"))
    REQUIRE_USER_VALIDATION = os.getenv("REQUIRE_USER_VALIDATION", "false").lower() == "true"
    REQUIRE_AGENT_VALIDATION = os.getenv("REQUIRE_AGENT_VALIDATION", "true").lower() == "true"
    VALIDATION_MODE = os.getenv("VALIDATION_MODE", "permissive")  # strict/permissive/disabled
    ENABLE_QUOTA_MANAGEMENT = os.getenv("ENABLE_QUOTA_MANAGEMENT", "true").lower() == "true"
    SEMANTIC_LAYER_DAILY_QUOTA = int(os.getenv("SEMANTIC_LAYER_DAILY_QUOTA", "1000"))

# Quota management with LRU cache
class QuotaManager:
    """Manages agent usage quotas with in-memory tracking"""
    
    def __init__(self, daily_limit: int = 1000):
        self.daily_limit = daily_limit
        self.usage = defaultdict(lambda: {"count": 0, "reset_time": None})
    
    def check_and_increment(self, agent_id: str) -> Dict[str, Any]:
        """
        Check if agent is within quota and increment usage.
        
        Returns:
            dict with 'allowed', 'current_usage', 'limit', 'reset_time'
        """
        now = datetime.utcnow()
        agent_usage = self.usage[agent_id]
        
        # Reset if past reset time
        if agent_usage["reset_time"] is None or now >= agent_usage["reset_time"]:
            agent_usage["count"] = 0
            agent_usage["reset_time"] = now + timedelta(days=1)
        
        # Check quota
        if agent_usage["count"] >= self.daily_limit:
            return {
                "allowed": False,
                "current_usage": agent_usage["count"],
                "limit": self.daily_limit,
                "reset_time": agent_usage["reset_time"].isoformat()
            }
        
        # Increment usage
        agent_usage["count"] += 1
        
        return {
            "allowed": True,
            "current_usage": agent_usage["count"],
            "limit": self.daily_limit,
            "reset_time": agent_usage["reset_time"].isoformat()
        }
    
    def get_usage(self, agent_id: str) -> Dict[str, Any]:
        """Get current usage for an agent"""
        agent_usage = self.usage[agent_id]
        return {
            "current_usage": agent_usage["count"],
            "limit": self.daily_limit,
            "reset_time": agent_usage["reset_time"].isoformat() if agent_usage["reset_time"] else None
        }

# Global quota manager instance
_quota_manager = QuotaManager(daily_limit=SEMANTIC_LAYER_DAILY_QUOTA)

class SemanticAccessValidator:
    """Validador de acceso semántico usando Guardian/OPA"""
    
    def __init__(self, guardian_url: str = None, opa_url: str = None, agent_cards_dir: str = None):
        self.guardian_url = guardian_url
        self.opa_url = opa_url
        self.agent_cards_dir = agent_cards_dir
        self.validation_cache = {}
        self.cache_ttl = 300  # 5 minutos
        
    async def validate_access(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validar acceso usando políticas OPA
        
        Args:
            request_context: Contexto del request con información del agente y usuario
            
        Returns:
            Dict con resultado de validación: {allowed: bool, reason: str, ...}
        """
        
        try:
            # Check if validation is disabled
            if VALIDATION_MODE == "disabled":
                abi_logging("[⚠️] Validation is DISABLED - allowing all access")
                return {
                    "allowed": True,
                    "reason": "Validation disabled",
                    "validation_mode": "disabled"
                }
            
            # Extraer información del agente
            agent_info = self._extract_agent_info(request_context)
            
            if not agent_info:
                return {
                    "allowed": False,
                    "reason": "Could not identify agent from request",
                    "error_code": "AGENT_IDENTIFICATION_FAILED",
                    "risk_score": 1.0
                }
            
            # Extraer información del usuario
            user_info = self._extract_user_info(request_context)
            
            # Validar usuario si está habilitado
            if REQUIRE_USER_VALIDATION or VALIDATION_MODE == "strict":
                if not user_info or not user_info.get("email"):
                    abi_logging(f"[❌] User validation required but no user email provided")
                    return {
                        "allowed": False,
                        "reason": "User email required for validation",
                        "error_code": "USER_EMAIL_REQUIRED",
                        "risk_score": 1.0
                    }
            
            # Check quota before proceeding (only if enabled)
            if ENABLE_QUOTA_MANAGEMENT:
                quota_check = _quota_manager.check_and_increment(agent_info["agent_id"])
                if not quota_check["allowed"]:
                    abi_logging(f"[⚠️] Quota exceeded for agent: {agent_info['agent_id']}")
                    return {
                        "allowed": False,
                        "reason": f"Daily quota exceeded ({quota_check['current_usage']}/{quota_check['limit']})",
                        "error_code": "QUOTA_EXCEEDED",
                        "risk_score": 0.8,
                        "quota_info": quota_check
                    }
            
            # Validar agente si está habilitado
            if REQUIRE_AGENT_VALIDATION:
                # Cargar agent card
                agent_card = await self._load_agent_card(agent_info["agent_id"])
                
                if not agent_card:
                    return {
                        "allowed": False,
                        "reason": f"Agent '{agent_info['agent_id']}' not registered in system",
                        "error_code": "AGENT_NOT_REGISTERED",
                        "risk_score": 1.0
                    }

                # Verify signature if payload is present
                if not self._verify_signature(agent_card, request_context):
                    return {
                        "allowed": False,
                        "reason": "Invalid agent signature",
                        "error_code": "INVALID_SIGNATURE",
                        "risk_score": 1.0,
                    }
            else:
                # If agent validation is disabled, create minimal agent card
                agent_card = {"id": agent_info["agent_id"], "name": "unknown"}
            
            # Preparar input para OPA
            opa_input = self._prepare_opa_input(agent_info, agent_card, request_context, user_info)
            
            # Evaluar políticas
            policy_result = await self._evaluate_opa_policy(opa_input)
            
            # Procesar resultado
            validation_result = self._process_policy_result(policy_result, agent_info, user_info)
            
            # Log resultado
            self._log_validation_result(validation_result, agent_info, user_info)
            
            return validation_result
            
        except Exception as e:
            abi_logging(f"🚨 Semantic access validation failed: {e}")
            return {
                "allowed": False,
                "reason": f"Validation service error: {str(e)}",
                "error_code": "VALIDATION_SERVICE_ERROR",
                "risk_score": 1.0
            }

    def _verify_signature(self, agent_card: dict, request_context: Dict[str, Any]) -> bool:
        """Verify HMAC signature if payload is present in request context.
        
        Returns True if:
        - No payload present (signature verification skipped)
        - Signature is valid
        
        Returns False if:
        - Payload present but signature missing or invalid
        """
        payload = request_context.get("payload")
        
        # If no payload, skip signature verification
        if not payload:
            return True
        
        auth = agent_card.get("auth", {})
        shared_secret = auth.get("shared_secret")
        
        if not shared_secret:
            abi_logging(f"⚠️ No shared_secret in agent card for signature verification")
            return False
        
        headers = request_context.get("headers", {})
        signature = headers.get("X-ABI-Signature")
        
        if not signature:
            abi_logging(f"⚠️ No X-ABI-Signature header present")
            return False

        expected = sign_payload_hmac(shared_secret, payload)
        is_valid = hmac.compare_digest(signature, expected)
        
        if not is_valid:
            abi_logging(f"❌ Signature verification failed for agent {agent_card.get('id')}")
        
        return is_valid


    def _extract_agent_info(self, request_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = request_context.get("headers", {})
        
        agent_id = headers.get("X-ABI-Agent-ID") or request_context.get("agent_id")
        key_id = headers.get("X-ABI-Key-Id")
        signature = headers.get("X-ABI-Signature")
        ts = headers.get("X-ABI-Timestamp")
        nonce = headers.get("X-ABI-Nonce")
        
        if not agent_id:
            abi_logging("❌ Could not extract agent ID from request context")
            abi_logging(f"Request context: {request_context}")
            return None
        
        return {
            "agent_id": agent_id.lower().strip(),
            "source_ip": request_context.get("client_ip", "unknown"),
            "user_agent": headers.get("X-Agent-Name") or headers.get("user-agent", "unknown"),
            "requested_tool": request_context.get("tool_name", "unknown"),
            "mcp_method": request_context.get("method", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "request_headers": headers
        }
    
    def _extract_user_info(self, request_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract user information from request context"""
        headers = request_context.get("headers", {})
        payload = request_context.get("payload", {})
        
        # Try to get user email from multiple sources
        user_email = (
            headers.get("X-ABI-User-Email") or
            request_context.get("user_email") or
            payload.get("user_email")
        )
        
        if not user_email:
            return None
        
        return {
            "email": user_email.lower().strip(),
            "authenticated": True,  # If email is present, assume authenticated
            "request_timestamp": datetime.utcnow().isoformat(),
            "source_ip": request_context.get("client_ip", "unknown")
        }
    
    async def _load_agent_card(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Cargar agent card desde filesystem"""
        
        try:
            # Buscar en cache primero
            cache_key = f"agent_card_{agent_id}"
            if cache_key in self.validation_cache:
                cached_entry = self.validation_cache[cache_key]
                if (datetime.utcnow().timestamp() - cached_entry["timestamp"]) < self.cache_ttl:
                    return cached_entry["data"]
            
            # Buscar archivo de agent card
            for card_file in self.agent_cards_dir.glob("*.json"):
                try:
                    with card_file.open() as f:
                        card_data = json.load(f)
                    
                    # Verificar coincidencia por ID o nombre
                    if (card_data.get("id") == agent_id or
                        "agent://"+card_data.get("name", "").lower().replace(" ", "_").strip() == agent_id):
                        
                        # Guardar en cache
                        self.validation_cache[cache_key] = {
                            "data": card_data,
                            "timestamp": datetime.utcnow().timestamp()
                        }
                        
                        abi_logging(f"📋 Loaded agent card for {agent_id}: {card_data.get('name')}")
                        return card_data
                        
                except json.JSONDecodeError as e:
                    abi_logging(f"⚠️ Invalid JSON in agent card file {card_file}: {e}")
                    continue
                except Exception as e:
                    abi_logging(f"⚠️ Error reading agent card file {card_file}: {e}")
                    continue
            
            abi_logging(f"🔍 No agent card found for: {agent_id}")
            return None
            
        except Exception as e:
            abi_logging(f"❌ Error loading agent card for {agent_id}: {e}")
            return None
    
    def _prepare_opa_input(self, agent_info: Dict[str, Any], agent_card: Dict[str, Any], request_context: Dict[str, Any], user_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Preparar input para evaluación OPA"""
        
        opa_input = {
            "action": "semantic_layer_access",
            "resource_type": "mcp_server",
            "source_agent": agent_info["agent_id"],
            "agent_card": agent_card,
            "request_metadata": {
                "timestamp": agent_info["timestamp"],
                "source_ip": agent_info["source_ip"],
                "user_agent": agent_info["user_agent"],
                "mcp_tool": agent_info["requested_tool"],
                "mcp_method": agent_info["mcp_method"],
                "headers": agent_info["request_headers"]
            },
            "context": {
                "service": "semantic_layer",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "validator_version": "1.0.0",
                "validation_mode": VALIDATION_MODE,
                "require_user_validation": REQUIRE_USER_VALIDATION,
                "require_agent_validation": REQUIRE_AGENT_VALIDATION
            }
        }
        
        # Add user information if available
        if user_info:
            opa_input["user"] = user_info
        
        return opa_input
    
    async def _evaluate_opa_policy(self, opa_input: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluar políticas usando OPA"""
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Llamar a OPA directamente
                response = await client.post(
                    f"{self.opa_url}/v1/data/abi/semantic_access",
                    json={"input": opa_input},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", {})
                else:
                    abi_logging(f"❌ OPA returned {response.status_code}: {response.text}")
                    return {"error": f"OPA service error: HTTP {response.status_code}"}
                    
        except httpx.TimeoutException:
            abi_logging("⏰ OPA policy evaluation timeout")
            return {"error": "OPA service timeout"}
        except Exception as e:
            abi_logging(f"❌ Failed to contact OPA: {e}")
            return {"error": f"OPA service unavailable: {str(e)}"}
    
    def _process_policy_result(self, policy_result: Dict[str, Any], agent_info: Dict[str, Any], user_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Procesar resultado de la evaluación de políticas"""
        
        if "error" in policy_result:
            result = {
                "allowed": False,
                "reason": policy_result["error"],
                "error_code": "POLICY_EVALUATION_ERROR",
                "risk_score": 1.0,
                "agent_id": agent_info["agent_id"]
            }
            if user_info:
                result["user_email"] = user_info["email"]
            return result
        
        # Extraer resultados de OPA
        allow = policy_result.get("allow", False)
        deny_reasons = policy_result.get("deny", [])
        risk_score = policy_result.get("risk_score", 1.0)
        audit_log = policy_result.get("audit_log", {})
        remediation = policy_result.get("remediation_suggestions", [])
        
        # Determinar si está permitido
        allowed = allow and len(deny_reasons) == 0
        
        # Determinar razón
        if allowed:
            reason = "Access granted by semantic access policy"
        else:
            if deny_reasons:
                reason = "; ".join(deny_reasons) if isinstance(deny_reasons, list) else str(deny_reasons)
            else:
                reason = "Access denied by semantic access policy"
        
        result = {
            "allowed": allowed,
            "reason": reason,
            "risk_score": risk_score,
            "agent_id": agent_info["agent_id"],
            "policy_evaluation": {
                "allow": allow,
                "deny_reasons": deny_reasons,
                "remediation_suggestions": remediation,
                "audit_log": audit_log
            },
            "validation_timestamp": datetime.utcnow().isoformat(),
            "validation_mode": VALIDATION_MODE
        }
        
        # Add user info if available
        if user_info:
            result["user_email"] = user_info["email"]
        
        return result
    
    def _log_validation_result(self, validation_result: Dict[str, Any], agent_info: Dict[str, Any], user_info: Optional[Dict[str, Any]] = None):
        """Log del resultado de validación"""
        
        agent_id = agent_info["agent_id"]
        allowed = validation_result["allowed"]
        reason = validation_result["reason"]
        risk_score = validation_result.get("risk_score", 0.0)
        
        # Build log message with user info if available
        user_str = f" | user: {user_info['email']}" if user_info else ""
        
        if allowed:
            abi_logging(f"✅ Semantic access granted for '{agent_id}'{user_str} (risk: {risk_score:.2f})")
        else:
            abi_logging(f"❌ Semantic access denied for '{agent_id}'{user_str}: {reason} (risk: {risk_score:.2f})")
        
        # Log adicional para debugging
        abi_logging(f"🔍 Validation details for {agent_id}: {validation_result}")

# Instancia global del validador
_validator = SemanticAccessValidator(GUARDIAN_URL, OPA_URL, AGENT_CARD_DIR)

def validate_semantic_access(func: Callable) -> Callable:
    """
    Decorador para validar acceso semántico usando políticas OPA
    
    Usage:
        @validate_semantic_access
        async def find_agent(query: str, _request_context: dict = None) -> dict:
            # Esta función solo se ejecutará si el agente está autorizado
            return search_agent(query)
    
    El decorador:
    1. Extrae información del agente del contexto del request
    2. Carga el agent card correspondiente
    3. Evalúa políticas OPA para determinar si se permite el acceso
    4. Si se permite, ejecuta la función original
    5. Si se deniega, retorna un error
    
    Note: All decorated functions must be async or will be converted to async.
    """
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        """Wrapper asíncrono"""
        
        # Extraer contexto del request
        request_context = kwargs.get("_request_context", {})
        
        # Si no hay contexto, intentar extraerlo de otros lugares
        if not request_context:
            # Buscar en argumentos
            for arg in args:
                if isinstance(arg, dict) and "headers" in arg:
                    request_context = arg
                    break
        
        # Validar acceso
        validation_result = await _validator.validate_access(request_context)
        
        if not validation_result["allowed"]:
            # Log the denial
            abi_logging(f"🚫 Access denied: {validation_result['reason']}")
            
            # Check return type annotation
            return_type = func.__annotations__.get("return") if hasattr(func, "__annotations__") else None
            
            # For Optional types, return None
            if return_type and "Optional" in str(return_type):
                return None
            
            # For dict types, return None (let caller handle)
            if return_type in [dict, Dict[str, Any], Optional[dict]]:
                return None
            
            # For list types, return empty list
            if return_type and ("list" in str(return_type) or "List" in str(return_type)):
                return []
            
            # Default: raise exception
            raise PermissionError(validation_result["reason"])
        
        # Si está autorizado, ejecutar función original
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Execute sync function in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    # Always return async wrapper - FastMCP handles async functions
    return async_wrapper
