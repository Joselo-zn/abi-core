"""
Configuration module for Builder Agent
Centralizes all environment variables and configuration settings
"""

import os
import json
from pathlib import Path

from a2a.types import AgentCard
from abi_core.common.agent_card_loader import load_agent_card


class AgentConfig:
    """Configuration class for Builder Agent"""

    # Agent Identity
    AGENT_NAME: str = "builder"
    AGENT_DISPLAY_NAME: str = "Builder Agent"
    AGENT_DESCRIPTION: str = "Builds and scaffolds ABI projects, agents, and services"

    # Ports
    AGENT_PORT: int = int(os.getenv('AGENT_PORT', '11439'))
    SERVICE_PORT: int = int(os.getenv('SERVICE_PORT', '11439'))

    # Model Configuration
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'qwen2.5:3b')
    OLLAMA_HOST: str = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    # LLM Configuration (unified dict for create_llm)
    LLM_CONFIG: dict = {
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "model": os.getenv("MODEL_NAME", "qwen2.5:3b"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
        "base_url": os.getenv("LLM_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "azure_deployment": os.getenv("AZURE_DEPLOYMENT", ""),
        "azure_endpoint": os.getenv("AZURE_ENDPOINT", ""),
        "vertex_project": os.getenv("VERTEX_PROJECT", ""),
        "vertex_location": os.getenv("VERTEX_LOCATION", "us-central1"),
    }

    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

    # ABI Configuration
    ABI_ROLE: str = os.getenv('ABI_ROLE', 'Builder Agent')
    ABI_NODE: str = os.getenv('ABI_NODE', 'ABI Node')

    # Semantic Layer / MCP
    SEMANTIC_LAYER_HOST: str = os.getenv('SEMANTIC_LAYER_HOST', 'http://localhost:10100')
    MCP_HOST: str = os.getenv('MCP_HOST', 'localhost')
    MCP_PORT: int = int(os.getenv('MCP_PORT', '10100'))
    MCP_TRANSPORT: str = os.getenv('MCP_TRANSPORT', 'streamable-http')

    # Agent Card
    AGENT_CARD: str = os.getenv('AGENT_CARD', './agent_cards/builder_agent.json')

    # A2A Validation
    A2A_VALIDATION_MODE: str = os.getenv('A2A_VALIDATION_MODE', 'permissive')
    A2A_ENABLE_AUDIT_LOG: bool = os.getenv('A2A_ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    GUARDIAN_URL: str = os.getenv('GUARDIAN_URL', 'http://localhost:11438')
    OPA_URL: str = os.getenv('OPA_URL', 'http://localhost:8181')

    # Logging & Observability
    LOG_TO_ARTIFACT_STORE: bool = os.getenv('LOG_TO_ARTIFACT_STORE', 'true').lower() == 'true'
    LOG_AGENT_NAME: str = os.getenv('LOG_AGENT_NAME', 'builder')
    LOG_BUCKET: str = os.getenv('LOG_BUCKET', 'abi-logs')

    # Ollama Configuration
    START_OLLAMA: bool = os.getenv('START_OLLAMA', 'false').lower() == 'true'
    LOAD_MODELS: bool = os.getenv('LOAD_MODELS', 'false').lower() == 'true'

    # Service Module
    SERVICE_MODULE: str = os.getenv('SERVICE_MODULE', 'main')

    @classmethod
    def get_ollama_url(cls) -> str:
        return cls.OLLAMA_HOST

    @classmethod
    def get_semantic_layer_url(cls) -> str:
        return cls.SEMANTIC_LAYER_HOST

    @classmethod
    def is_distributed_mode(cls) -> bool:
        return cls.START_OLLAMA

    @classmethod
    def display_config(cls) -> dict:
        return {
            'agent_name': cls.AGENT_NAME,
            'agent_display_name': cls.AGENT_DISPLAY_NAME,
            'agent_port': cls.AGENT_PORT,
            'model_name': cls.MODEL_NAME,
            'ollama_host': cls.OLLAMA_HOST,
            'semantic_layer_host': cls.SEMANTIC_LAYER_HOST,
            'log_level': cls.LOG_LEVEL,
            'distributed_mode': cls.is_distributed_mode(),
        }


config = AgentConfig()


def _load_agent_card() -> AgentCard:
    """Load and validate the agent card from file."""
    card, _meta = load_agent_card(config.AGENT_CARD)

    if card.name != config.AGENT_DISPLAY_NAME:
        raise ValueError(
            f"Agent card name mismatch. "
            f"Expected: {config.AGENT_DISPLAY_NAME}, Got: {card.name}"
        )

    return card


AGENT_CARD = _load_agent_card()
