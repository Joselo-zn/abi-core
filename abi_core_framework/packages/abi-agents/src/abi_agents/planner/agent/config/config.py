"""
Configuration module for Planner Agent
Centralizes all environment variables and configuration settings
"""

import os
import json
from pathlib import Path
from typing import Optional

from a2a.types import AgentCard
from abi_core.common.agent_card_loader import load_agent_card
from abi_core.common.prompts import PLANNER_COT_INSTRUCTIONS, TECHNICAL_DESIGN_INSTRUCTIONS

from prompts import build_planning_query, build_direct_tool_content_prompt, build_technical_design_query
from abi_core.agent.llm_provider import llm_config_from_env


class AgentConfig:
    """Configuration class for Planner Agent"""
    
    # Agent Identity
    AGENT_NAME: str = "planner"
    AGENT_DISPLAY_NAME: str = "Abi Planner Agent"
    AGENT_DESCRIPTION: str = "Decomposes tasks and assigns agents"
    
    # Ports
    AGENT_PORT: int = int(os.getenv('AGENT_PORT', '11437'))
    SERVICE_PORT: int = int(os.getenv('SERVICE_PORT', '11437'))
    
    # Model Configuration
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'qwen3:latest')
    OLLAMA_HOST: str = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    # LLM Configuration (unified dict for create_llm)
    # LLM settings from the environment (LLM_PROVIDER, MODEL_NAME, LLM_BASE_URL,
    # LLM_API_KEY, LLM_TEMPERATURE, LLM_EXTRA_PARAMS — a JSON object passed
    # as-is to the LangChain model). See abi_core.agent.llm_provider.
    LLM_CONFIG: dict = llm_config_from_env()
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # ABI Configuration
    ABI_ROLE: str = os.getenv('ABI_ROLE', 'Planner Agent')
    ABI_NODE: str = os.getenv('ABI_NODE', 'ABI Node')
    
    # Semantic Layer / MCP
    SEMANTIC_LAYER_HOST: str = os.getenv('SEMANTIC_LAYER_HOST', 'http://localhost:10100')
    MCP_HOST: str = os.getenv('MCP_HOST', 'localhost')
    MCP_PORT: int = int(os.getenv('MCP_PORT', '10100'))
    MCP_TRANSPORT: str = os.getenv('MCP_TRANSPORT', 'streamable-http')
    
    # Agent Card
    AGENT_CARD: str = os.getenv('AGENT_CARD', './agent_cards/planner_agent.json')
    
    # A2A Validation
    A2A_VALIDATION_MODE: str = os.getenv('A2A_VALIDATION_MODE', 'permissive')
    A2A_ENABLE_AUDIT_LOG: bool = os.getenv('A2A_ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    GUARDIAN_URL: str = os.getenv('GUARDIAN_URL', 'http://localhost:11438')
    OPA_URL: str = os.getenv('OPA_URL', 'http://localhost:8181')
    
    # Ollama Configuration (for distributed mode)
    START_OLLAMA: bool = os.getenv('START_OLLAMA', 'false').lower() == 'true'
    LOAD_MODELS: bool = os.getenv('LOAD_MODELS', 'false').lower() == 'true'
    
    # Service Module
    SERVICE_MODULE: str = os.getenv('SERVICE_MODULE', 'main')

    # Prompts (see agent/prompts.py) — centralized here so planner.py reads
    # all prompt content through config instead of importing prompt modules
    # directly.
    SYSTEM_PROMPT: str = PLANNER_COT_INSTRUCTIONS
    TECHNICAL_DESIGN_PROMPT: str = TECHNICAL_DESIGN_INSTRUCTIONS
    build_planning_query = staticmethod(build_planning_query)
    build_technical_design_query = staticmethod(build_technical_design_query)
    build_direct_tool_content_prompt = staticmethod(build_direct_tool_content_prompt)

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
    """Load and validate the agent card from file."""
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
