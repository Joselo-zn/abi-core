# Semantic Layer Access Control Policies
# Controla el acceso de agentes a la capa semántica via MCP

package abi.semantic_access

import rego.v1

# Default deny - solo agentes autorizados pueden acceder
default allow := false
default deny := false
default risk_score := 1.0

# =============================================================================
# REGLAS DE ACCESO PRINCIPAL
# =============================================================================

# Permitir acceso si el agente está registrado y no hay violaciones
allow if {
    agent_registered
    not agent_blacklisted
    not agent_inactive
    not rate_limit_exceeded
    not unauthorized_ip
    not outside_schedule
    not insufficient_permissions
}

# =============================================================================
# VERIFICACIONES DE AGENTE
# =============================================================================

# Verificar que el agente esté registrado en el sistema
agent_registered if {
    input.source_agent
    input.agent_card
    input.agent_card.id
    # Verificar que el ID del agent card coincida con el agente solicitante
    agent_id_matches
}

# Verificar coincidencia de ID de agente
agent_id_matches if {
    input.agent_card.id == sprintf("agent://%s", [input.source_agent])
}

agent_id_matches if {
    input.agent_card.name
    lower(input.agent_card.name) == lower(sprintf("%s agent", [input.source_agent]))
}

# =============================================================================
# REGLAS DE DENEGACIÓN
# =============================================================================

# Denegar si el agente está en lista negra
deny contains "Agent is blacklisted" if {
    agent_blacklisted
}

agent_blacklisted if {
    input.source_agent in data.blacklisted_agents
}

agent_blacklisted if {
    input.agent_card.metadata.status == "blacklisted"
}

# Denegar si el agente está marcado como inactivo
deny contains "Agent marked as inactive" if {
    agent_inactive
}

agent_inactive if {
    input.agent_card.metadata.status == "inactive"
}

agent_inactive if {
    input.agent_card.metadata.enabled == false
}

# Denegar si se excede el rate limit
deny contains "Rate limit exceeded for agent" if {
    rate_limit_exceeded
}

rate_limit_exceeded if {
    input.source_agent
    agent_request_count := data.agent_request_counts[input.source_agent]
    rate_limit := data.rate_limits.requests_per_minute
    agent_request_count > rate_limit
}

# Denegar acceso desde IP no autorizada
deny contains "Unauthorized source IP address" if {
    unauthorized_ip
}

unauthorized_ip if {
    input.request_metadata.source_ip
    input.agent_card.security
    input.agent_card.security.allowed_ips
    count(input.agent_card.security.allowed_ips) > 0
    not input.request_metadata.source_ip in input.agent_card.security.allowed_ips
}

# Denegar acceso fuera de horario permitido
deny contains "Access outside allowed schedule" if {
    outside_schedule
}

outside_schedule if {
    input.agent_card.security
    input.agent_card.security.access_schedule
    not within_allowed_schedule(input.agent_card.security.access_schedule)
}

# Denegar si el agente no tiene permisos para la herramienta MCP solicitada
deny contains "Insufficient permissions for requested MCP tool" if {
    insufficient_permissions
}

insufficient_permissions if {
    input.request_metadata.mcp_tool
    input.agent_card.security
    input.agent_card.security.allowed_mcp_tools
    count(input.agent_card.security.allowed_mcp_tools) > 0
    not input.request_metadata.mcp_tool in input.agent_card.security.allowed_mcp_tools
}

# =============================================================================
# CÁLCULO DE RIESGO
# =============================================================================

# Calcular score de riesgo basado en múltiples factores
risk_score := calculated_risk if {
    base_risk := base_risk_score
    ip_risk := ip_risk_modifier
    time_risk := time_risk_modifier
    tool_risk := tool_risk_modifier
    agent_risk := agent_risk_modifier
    
    calculated_risk := min([1.0, base_risk + ip_risk + time_risk + tool_risk + agent_risk])
}

# Riesgo base por acción
base_risk_score := score if {
    action_scores := {
        "semantic_layer_access": 0.2,
        "find_agent": 0.1,
        "get_agent_card": 0.1,
        "list_agents": 0.15,
        "register_agent": 0.6,
        "unregister_agent": 0.8
    }
    score := action_scores[input.action]
}

base_risk_score := 0.3 if {
    not input.action
}

# Modificador de riesgo por IP
ip_risk_modifier := 0.2 if {
    input.request_metadata.source_ip
    input.request_metadata.source_ip == "unknown"
}

ip_risk_modifier := 0.1 if {
    input.request_metadata.source_ip
    not is_internal_ip(input.request_metadata.source_ip)
}

ip_risk_modifier := 0.0 if {
    input.request_metadata.source_ip
    is_internal_ip(input.request_metadata.source_ip)
}

# Modificador de riesgo por horario
time_risk_modifier := 0.1 if {
    current_hour := time.clock(time.now_ns())[0]
    # Horario de riesgo: 22:00 - 06:00
    current_hour >= 22
}

time_risk_modifier := 0.1 if {
    current_hour := time.clock(time.now_ns())[0]
    current_hour <= 6
}

time_risk_modifier := 0.0 if {
    current_hour := time.clock(time.now_ns())[0]
    current_hour > 6
    current_hour < 22
}

# Modificador de riesgo por herramienta MCP
tool_risk_modifier := score if {
    tool_scores := {
        "find_agent": 0.0,
        "get_agent_card": 0.0,
        "list_agents": 0.05,
        "register_agent": 0.3,
        "unregister_agent": 0.4,
        "unknown": 0.2
    }
    tool := input.request_metadata.mcp_tool
    score := tool_scores[tool]
}

tool_risk_modifier := 0.2 if {
    not input.request_metadata.mcp_tool
}

# Modificador de riesgo por agente
agent_risk_modifier := 0.0 if {
    input.source_agent in trusted_agents
}

agent_risk_modifier := 0.1 if {
    not input.source_agent in trusted_agents
    input.agent_card.metadata.trust_level == "medium"
}

agent_risk_modifier := 0.2 if {
    not input.source_agent in trusted_agents
    input.agent_card.metadata.trust_level == "low"
}

agent_risk_modifier := 0.05 if {
    not input.source_agent in trusted_agents
    not input.agent_card.metadata.trust_level
}

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

# Verificar si está dentro del horario permitido
within_allowed_schedule(schedule) if {
    current_hour := time.clock(time.now_ns())[0]
    current_hour >= schedule.start_hour
    current_hour <= schedule.end_hour
}

# Verificar si es IP interna
is_internal_ip(ip) if {
    # Rangos de IP privadas
    regex.match(`^10\.`, ip)
}

is_internal_ip(ip) if {
    regex.match(`^192\.168\.`, ip)
}

is_internal_ip(ip) if {
    regex.match(`^172\.(1[6-9]|2[0-9]|3[0-1])\.`, ip)
}

is_internal_ip(ip) if {
    ip == "127.0.0.1"
}

is_internal_ip(ip) if {
    ip == "localhost"
}

# Lista de agentes de confianza
trusted_agents := {
    "orchestrator",
    "planner", 
    "observer"
}

# =============================================================================
# DATOS DE CONFIGURACIÓN POR DEFECTO
# =============================================================================

# Configuración por defecto si no hay datos externos
default_rate_limits := {
    "requests_per_minute": 60
}

default_blacklisted_agents := set()

# =============================================================================
# REGISTRO DE AUDITORÍA
# =============================================================================

# Generar log de auditoría estructurado
audit_log := {
    "timestamp": time.now_ns(),
    "policy": "semantic_access",
    "version": "1.0.0",
    "decision": {
        "allow": allow,
        "deny": deny,
        "risk_score": risk_score,
        "denial_reasons": deny
    },
    "evaluation": {
        "agent_registered": agent_registered,
        "agent_blacklisted": agent_blacklisted,
        "agent_inactive": agent_inactive,
        "rate_limit_exceeded": rate_limit_exceeded,
        "unauthorized_ip": unauthorized_ip,
        "outside_schedule": outside_schedule,
        "insufficient_permissions": insufficient_permissions
    },
    "risk_factors": {
        "base_risk": base_risk_score,
        "ip_risk": ip_risk_modifier,
        "time_risk": time_risk_modifier,
        "tool_risk": tool_risk_modifier,
        "agent_risk": agent_risk_modifier
    },
    "input_summary": {
        "source_agent": input.source_agent,
        "action": input.action,
        "mcp_tool": input.request_metadata.mcp_tool,
        "source_ip": input.request_metadata.source_ip,
        "agent_card_present": input.agent_card != null
    }
}

# =============================================================================
# SUGERENCIAS DE REMEDIACIÓN
# =============================================================================

remediation_suggestions contains "Register agent in the system" if {
    not agent_registered
}

remediation_suggestions contains "Remove agent from blacklist" if {
    agent_blacklisted
}

remediation_suggestions contains "Activate agent in system" if {
    agent_inactive
}

remediation_suggestions contains "Reduce request rate or increase rate limit" if {
    rate_limit_exceeded
}

remediation_suggestions contains "Access from authorized IP address" if {
    unauthorized_ip
}

remediation_suggestions contains "Access during allowed schedule hours" if {
    outside_schedule
}

remediation_suggestions contains "Request access permissions for MCP tool" if {
    insufficient_permissions
}

remediation_suggestions contains "Contact system administrator for access review" if {
    risk_score > 0.8
}