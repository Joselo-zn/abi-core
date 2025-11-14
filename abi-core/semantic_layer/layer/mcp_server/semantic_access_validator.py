"""
Decorador para validación de acceso semántico usando políticas OPA
"""

import os
import json
import logging
import asyncio
import httpx
from functools import wraps
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class SemanticAccessValidator:
    """Validador de acceso semántico usando Guardian/OPA"""
    
    def __init__(self):
        self.guardian_url = os.getenv("GUARDIAN_URL", "http://abi-guardial:11438")
        self.opa_url = os.getenv("OPA_URL", "http://abi-opa:8181")
        self.agent_cards_dir = Path(os.getenv("AGENT_CARDS_BASE", "/app/agent_cards"))
        self.validation_cache = {}
        self.cache_ttl = 300  # 5 minutos
        
    async def validate_access(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validar acceso usando políticas OPA
        
        Args:
            request_context: Contexto del request con información del agente
            
        Returns:
            Dict con resultado de validación: {allowed: bool, reason: str, ...}
        """
        
        try:
            # Extraer información del agente
            agent_info = self._extract_agent_info(request_context)
            
            if not agent_info:
                return {
                    "allowed": False,
                    "reason": "Could not identify agent from request",
                    "error_code": "AGENT_IDENTIFICATION_FAILED",
                    "risk_score": 1.0
                }
            
            # Cargar agent card
            agent_card = await self._load_agent_card(agent_info["agent_id"])
            
            if not agent_card:
                return {
                    "allowed": False,
                    "reason": f"Agent '{agent_info['agent_id']}' not registered in system",
                    "error_code": "AGENT_NOT_REGISTERED",
                    "risk_score": 1.0
                }
            
            # Preparar input para OPA
            opa_input = self._prepare_opa_input(agent_info, agent_card, request_context)
            
            # Evaluar políticas
            policy_result = await self._evaluate_opa_policy(opa_input)
            
            # Procesar resultado
            validation_result = self._process_policy_result(policy_result, agent_info)
            
            # Log resultado
            self._log_validation_result(validation_result, agent_info)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"🚨 Semantic access validation failed: {e}")
            return {
                "allowed": False,
                "reason": f"Validation service error: {str(e)}",
                "error_code": "VALIDATION_SERVICE_ERROR",
                "risk_score": 1.0
            }
    
    def _extract_agent_info(self, request_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extraer información del agente del contexto del request"""
        
        # Obtener headers del contexto
        headers = request_context.get("headers", {})
        
        # Método 1: Header X-Agent-ID
        agent_id = headers.get("x-agent-id") or headers.get("X-Agent-ID")
        
        # Método 2: User-Agent parsing
        if not agent_id:
            user_agent = headers.get("user-agent", "")
            if "ABI-Agent" in user_agent:
                # Parse: "ABI-Agent/planner/1.0"
                parts = user_agent.split("/")
                if len(parts) >= 2:
                    agent_id = parts[1]
        
        # Método 3: Desde metadata del request
        if not agent_id:
            agent_id = request_context.get("agent_id")
        
        # Método 4: Inferir desde el contexto de la función
        if not agent_id:
            # Último recurso: usar información del caller
            caller_info = request_context.get("caller_info", {})
            agent_id = caller_info.get("agent_name")
        
        if not agent_id:
            logger.warning("❌ Could not extract agent ID from request context")
            logger.debug(f"Request context: {request_context}")
            return None
        
        return {
            "agent_id": agent_id.lower().strip(),
            "source_ip": request_context.get("client_ip", "unknown"),
            "user_agent": headers.get("user-agent", ""),
            "requested_tool": request_context.get("tool_name", "unknown"),
            "mcp_method": request_context.get("method", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "request_headers": headers
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
                    if (card_data.get("id") == f"agent://{agent_id}" or
                        card_data.get("id") == agent_id or
                        card_data.get("name", "").lower().replace(" agent", "").strip() == agent_id):
                        
                        # Guardar en cache
                        self.validation_cache[cache_key] = {
                            "data": card_data,
                            "timestamp": datetime.utcnow().timestamp()
                        }
                        
                        logger.debug(f"📋 Loaded agent card for {agent_id}: {card_data.get('name')}")
                        return card_data
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in agent card file {card_file}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error reading agent card file {card_file}: {e}")
                    continue
            
            logger.warning(f"🔍 No agent card found for: {agent_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading agent card for {agent_id}: {e}")
            return None
    
    def _prepare_opa_input(self, agent_info: Dict[str, Any], agent_card: Dict[str, Any], request_context: Dict[str, Any]) -> Dict[str, Any]:
        """Preparar input para evaluación OPA"""
        
        return {
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
                "validator_version": "1.0.0"
            }
        }
    
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
                    logger.error(f"OPA returned {response.status_code}: {response.text}")
                    return {"error": f"OPA service error: HTTP {response.status_code}"}
                    
        except httpx.TimeoutException:
            logger.error("OPA policy evaluation timeout")
            return {"error": "OPA service timeout"}
        except Exception as e:
            logger.error(f"Failed to contact OPA: {e}")
            return {"error": f"OPA service unavailable: {str(e)}"}
    
    def _process_policy_result(self, policy_result: Dict[str, Any], agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Procesar resultado de la evaluación de políticas"""
        
        if "error" in policy_result:
            return {
                "allowed": False,
                "reason": policy_result["error"],
                "error_code": "POLICY_EVALUATION_ERROR",
                "risk_score": 1.0,
                "agent_id": agent_info["agent_id"]
            }
        
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
        
        return {
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
            "validation_timestamp": datetime.utcnow().isoformat()
        }
    
    def _log_validation_result(self, validation_result: Dict[str, Any], agent_info: Dict[str, Any]):
        """Log del resultado de validación"""
        
        agent_id = agent_info["agent_id"]
        allowed = validation_result["allowed"]
        reason = validation_result["reason"]
        risk_score = validation_result.get("risk_score", 0.0)
        
        if allowed:
            logger.info(f"✅ Semantic access granted for '{agent_id}' (risk: {risk_score:.2f})")
        else:
            logger.warning(f"❌ Semantic access denied for '{agent_id}': {reason} (risk: {risk_score:.2f})")
        
        # Log adicional para debugging
        logger.debug(f"Validation details for {agent_id}: {validation_result}")

# Instancia global del validador
_validator = SemanticAccessValidator()

def validate_semantic_access(func: Callable) -> Callable:
    """
    Decorador para validar acceso semántico usando políticas OPA
    
    Usage:
        @validate_semantic_access
        def find_agent(query: str) -> dict:
            # Esta función solo se ejecutará si el agente está autorizado
            return search_agent(query)
    
    El decorador:
    1. Extrae información del agente del contexto del request
    2. Carga el agent card correspondiente
    3. Evalúa políticas OPA para determinar si se permite el acceso
    4. Si se permite, ejecuta la función original
    5. Si se deniega, retorna un error
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
            # Retornar error en formato apropiado
            error_response = {
                "error": {
                    "code": validation_result.get("error_code", "ACCESS_DENIED"),
                    "message": validation_result["reason"],
                    "agent_id": validation_result.get("agent_id"),
                    "risk_score": validation_result.get("risk_score", 1.0),
                    "timestamp": validation_result.get("validation_timestamp")
                }
            }
            
            # Para funciones que retornan dict, retornar el error
            if hasattr(func, "__annotations__") and func.__annotations__.get("return") in [dict, Dict[str, Any], Optional[dict]]:
                return error_response
            else:
                # Para otras funciones, lanzar excepción
                raise PermissionError(validation_result["reason"])
        
        # Si está autorizado, ejecutar función original
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        """Wrapper síncrono"""
        
        # Para funciones síncronas, ejecutar validación en loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(async_wrapper(*args, **kwargs))
    
    # Retornar wrapper apropiado según si la función es async o no
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# Función auxiliar para inyectar contexto en requests
def with_agent_context(agent_id: str, **additional_context):
    """
    Helper para inyectar contexto de agente en requests
    
    Usage:
        context = with_agent_context("planner", tool_name="find_agent")
        result = find_agent("search query", _request_context=context)
    """
    
    return {
        "agent_id": agent_id,
        "headers": {
            "X-Agent-ID": agent_id,
            "User-Agent": f"ABI-Agent/{agent_id}/1.0"
        },
        "timestamp": datetime.utcnow().isoformat(),
        **additional_context
    }