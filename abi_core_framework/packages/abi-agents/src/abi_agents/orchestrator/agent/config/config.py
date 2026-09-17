"""
Configuration module for Orchestrator Agent
Centralizes all environment variables and configuration settings
"""

import os
import json
from pathlib import Path
from typing import Optional

from a2a.types import AgentCard
from abi_core.common.agent_card_loader import load_agent_card


class AgentConfig:
    """Configuration class for Orchestrator Agent"""
    
    # Agent Identity
    AGENT_NAME: str = "orchestrator"
    AGENT_DISPLAY_NAME: str = "Abi Orchestrator Agent"
    AGENT_DESCRIPTION: str = "Coordinates multi-agent workflow execution"
    
    # Ports
    AGENT_PORT: int = int(os.getenv('AGENT_PORT', '8002'))
    SERVICE_PORT: int = int(os.getenv('SERVICE_PORT', '8002'))
    WEB_INTERFACE_PORT: int = int(os.getenv('WEB_INTERFACE_PORT', '8083'))
    
    # Model Configuration
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'qwen3:latest')
    OLLAMA_HOST: str = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    # reasoning=False is an Ollama/qwen3-specific kwarg (disables "thinking"
    # mode — see the LLM_CONFIG comment below for why). Only valid for
    # ChatOllama; forwarding it to another provider's constructor (e.g.
    # ChatAnthropic) via extra_params would error or be silently rejected.
    # Gate it on the actual provider instead of hardcoding it.
    _OLLAMA_EXTRA_PARAMS: dict = {"reasoning": False}

    # LLM Configuration (unified dict for create_llm)
    LLM_CONFIG: dict = {
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "model": os.getenv("MODEL_NAME", "qwen3:latest"),
        # None (unset) lets create_llm() omit temperature entirely, so the
        # provider uses its own default — required for e.g. Claude models
        # with extended thinking, which reject any explicit temperature
        # other than 1. Set LLM_TEMPERATURE explicitly to override.
        "temperature": float(os.environ["LLM_TEMPERATURE"]) if os.getenv("LLM_TEMPERATURE") else None,
        "base_url": os.getenv("LLM_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "azure_deployment": os.getenv("AZURE_DEPLOYMENT", ""),
        "azure_endpoint": os.getenv("AZURE_ENDPOINT", ""),
        "vertex_project": os.getenv("VERTEX_PROJECT", ""),
        "vertex_location": os.getenv("VERTEX_LOCATION", "us-central1"),
        # Provider- or model-generation-specific kwargs forwarded as-is to
        # the LangChain chat model constructor (e.g. Claude's `thinking`,
        # Gemini's `thinking_budget`/`thinking_level`, Azure's
        # `api_version`). Edit this dict directly for your deployment.
        #
        # See .abi/tsd/2026-09-09-routing-decision-model-profiling.md for
        # why qwen3 needs reasoning=False (thinking mode ON by default costs
        # ~277s/call vs ~13s off, with no accuracy benefit, on EVERY
        # reasoning turn — not just plan approval — which reliably triggers
        # Chainlit's own ~60s disconnect bug #2108).
        "extra_params": _OLLAMA_EXTRA_PARAMS if os.getenv("LLM_PROVIDER", "ollama") == "ollama" else {},
    }

    # Model used ONLY for the resolve_pending_plan structured decision — the
    # highest-stakes routing decision (a false "approve" triggers real
    # build_workflow/Docker execution). Profiled empirically against
    # qwen3:latest (Ollama): 4/10 correct on approve phrasings with thinking
    # on, vs 9/10 with reasoning disabled. Bigger local models (granite4.1:8b,
    # devstral:24b) did NOT close the gap — this is about capability profile,
    # not raw size. See .abi/specs/orchestrator-unified-routing-contract.md.
    ROUTING_DECISION_MODEL_NAME: str = os.getenv("ROUTING_DECISION_MODEL_NAME", "qwen3:latest")
    ROUTING_DECISION_LLM_CONFIG: dict = {
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "model": os.getenv("ROUTING_DECISION_MODEL_NAME", "qwen3:latest"),
        "temperature": float(os.environ["LLM_TEMPERATURE"]) if os.getenv("LLM_TEMPERATURE") else None,
        "base_url": os.getenv("LLM_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "extra_params": _OLLAMA_EXTRA_PARAMS if os.getenv("LLM_PROVIDER", "ollama") == "ollama" else {},
    }

    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # ABI Configuration
    ABI_ROLE: str = os.getenv('ABI_ROLE', 'Orchestrator Agent')
    ABI_NODE: str = os.getenv('ABI_NODE', 'ABI Node')
    
    # Semantic Layer / MCP
    SEMANTIC_LAYER_HOST: str = os.getenv('SEMANTIC_LAYER_HOST', 'http://localhost:10100')
    MCP_HOST: str = os.getenv('MCP_HOST', 'localhost')
    MCP_PORT: int = int(os.getenv('MCP_PORT', '10100'))
    MCP_TRANSPORT: str = os.getenv('MCP_TRANSPORT', 'streamable-http')
    
    # Agent Card
    AGENT_CARD: str = os.getenv('AGENT_CARD', './agent_cards/orchestrator_agent.json')
    
    # A2A Validation
    A2A_VALIDATION_MODE: str = os.getenv('A2A_VALIDATION_MODE', 'permissive')
    A2A_ENABLE_AUDIT_LOG: bool = os.getenv('A2A_ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    GUARDIAN_URL: str = os.getenv('GUARDIAN_URL', 'http://localhost:11438')
    OPA_URL: str = os.getenv('OPA_URL', 'http://localhost:8181')
    
    # Logging & Observability
    LOG_TO_ARTIFACT_STORE: bool = os.getenv('LOG_TO_ARTIFACT_STORE', 'true').lower() == 'true'
    LOG_AGENT_NAME: str = os.getenv('LOG_AGENT_NAME', 'orchestrator')
    LOG_BUCKET: str = os.getenv('LOG_BUCKET', 'abi-logs')
    
    # Artifact Store (MinIO/S3)
    ARTIFACT_ENDPOINT: str = os.getenv('ARTIFACT_ENDPOINT', 'http://localhost:9000')
    ARTIFACT_ACCESS_KEY: str = os.getenv('ARTIFACT_ACCESS_KEY', 'minioadmin')
    ARTIFACT_SECRET_KEY: str = os.getenv('ARTIFACT_SECRET_KEY', 'minioadmin')
    ARTIFACT_BUCKET: str = os.getenv('ARTIFACT_BUCKET', 'abi-artifacts')
    
    # Ephemeral Agent Control
    EPHEMERAL_AUTO_DESTROY: bool = os.getenv('EPHEMERAL_AUTO_DESTROY', 'true').lower() == 'true'

    # Agent Memory (Redis AMS) — system-wide short/long-term memory
    AGENT_MEMORY_URL: str = os.getenv('AGENT_MEMORY_URL', '')

    # Session Management (framework-managed, LB/multi-pod safe)
    # SESSION_BACKEND: "memory" (per-pod, dev) | "redis" (shared, multi-pod).
    SESSION_BACKEND: str = os.getenv('SESSION_BACKEND', 'memory')
    SESSION_TTL: int = int(os.getenv('SESSION_TTL', '3600'))
    SESSION_REDIS_URL: str = os.getenv('SESSION_REDIS_URL', os.getenv('REDIS_URL', ''))
    ABI_SESSION_REQUIRED: bool = os.getenv('ABI_SESSION_REQUIRED', 'false').lower() == 'true'

    # Conversation memory (AbiAgent.record_conversation_turn) — how many
    # recent turns stay in the active session window before the oldest is
    # promoted to AMS long-term memory. See
    # .abi/specs/orchestrator-conversation-memory.md.
    CONVERSATION_WINDOW: int = int(os.getenv('CONVERSATION_WINDOW', '5'))

    # Ollama Configuration (for distributed mode)
    START_OLLAMA: bool = os.getenv('START_OLLAMA', 'false').lower() == 'true'
    LOAD_MODELS: bool = os.getenv('LOAD_MODELS', 'false').lower() == 'true'
    
    # Service Module
    SERVICE_MODULE: str = os.getenv('SERVICE_MODULE', 'main')
    
    @classmethod
    def get_ollama_url(cls) -> str:
        """Get the complete Ollama URL"""
        return cls.OLLAMA_HOST
    
    @classmethod
    def get_semantic_layer_url(cls) -> str:
        """Get the complete Semantic Layer URL"""
        return cls.SEMANTIC_LAYER_HOST
    
    @classmethod
    def is_distributed_mode(cls) -> bool:
        """Check if running in distributed Ollama mode"""
        return cls.START_OLLAMA
    
    @classmethod
    def display_config(cls) -> dict:
        """Return configuration as dictionary for display"""
        return {
            'agent_name': cls.AGENT_NAME,
            'agent_display_name': cls.AGENT_DISPLAY_NAME,
            'agent_port': cls.AGENT_PORT,
            'web_interface_port': cls.WEB_INTERFACE_PORT,
            'model_name': cls.MODEL_NAME,
            'ollama_host': cls.OLLAMA_HOST,
            'semantic_layer_host': cls.SEMANTIC_LAYER_HOST,
            'log_level': cls.LOG_LEVEL,
            'distributed_mode': cls.is_distributed_mode()
        }


# Create a singleton instance
config = AgentConfig()


# Load agent card at module import time
def _load_agent_card() -> AgentCard:
    """
    Load and validate the agent card from file
    """
    card, _meta = load_agent_card(config.AGENT_CARD)
    
    if card.name != config.AGENT_DISPLAY_NAME:
        raise ValueError(
            f"Agent card name mismatch. "
            f"Expected: {config.AGENT_DISPLAY_NAME}, "
            f"Got: {card.name}"
        )
    
    return card


# Agent card loaded at import time - ready to use
AGENT_CARD = _load_agent_card()
