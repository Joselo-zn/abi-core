"""
Configuration module for Guardian Agent.
Centralizes all environment variables and configuration settings.
"""

import os
import json
from pathlib import Path


class GuardianConfig:
    """Configuration class for Guardian Agent."""

    # Service Identity
    AGENT_NAME: str = "guardian"
    AGENT_DESCRIPTION: str = "Security policy enforcement and compliance validation"
    AGENT_DISPLAY_NAME: str = os.getenv("GUARDIAN_DISPLAY_NAME", "ABI Guardian")

    # Server Configuration
    HOST: str = os.getenv("GUARDIAN_HOST", "0.0.0.0")
    AGENT_PORT: int = int(os.getenv("GUARDIAN_PORT", "11438"))
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    # OPA Configuration
    OPA_HOST: str = os.getenv("OPA_HOST", "0.0.0.0")
    OPA_PORT: int = int(os.getenv("OPA_PORT", "8181"))
    OPA_URL: str = os.getenv("OPA_URL", f"http://{OPA_HOST}:{OPA_PORT}")

    # LLM Configuration
    LLM_CONFIG: dict = {
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "model": os.getenv("MODEL_NAME", "qwen2.5:3b"),
        "temperature": 0.0,
        "base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    }

    # Policy Configuration
    POLICIES_DIR: str = os.getenv("POLICIES_DIR", "/app/policies")
    AUTO_RELOAD_POLICIES: bool = os.getenv("AUTO_RELOAD_POLICIES", "true").lower() == "true"
    POLICY_RELOAD_INTERVAL: int = int(os.getenv("POLICY_RELOAD_INTERVAL", "60"))

    # Validation Configuration
    ENABLE_AGENT_VALIDATION: bool = os.getenv("ENABLE_AGENT_VALIDATION", "true").lower() == "true"
    ENABLE_RESOURCE_VALIDATION: bool = os.getenv("ENABLE_RESOURCE_VALIDATION", "true").lower() == "true"

    # Security
    REQUIRE_AUTHENTICATION: bool = os.getenv("REQUIRE_AUTHENTICATION", "true").lower() == "true"
    ENABLE_AUDIT_LOG: bool = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"

    # Risk Scoring
    HIGH_RISK_THRESHOLD: float = float(os.getenv("HIGH_RISK_THRESHOLD", "0.7"))
    MEDIUM_RISK_THRESHOLD: float = float(os.getenv("MEDIUM_RISK_THRESHOLD", "0.4"))

    # Agent Card
    AGENT_CARD_PATH: str = os.getenv("AGENT_CARD", "./agent/agent_cards/guardian_agent.json")

    @classmethod
    def get_risk_level(cls, score: float) -> str:
        if score >= cls.HIGH_RISK_THRESHOLD:
            return "HIGH"
        elif score >= cls.MEDIUM_RISK_THRESHOLD:
            return "MEDIUM"
        return "LOW"


config = GuardianConfig()


def _load_agent_card():
    from a2a.types import AgentCard

    card_path = Path(config.AGENT_CARD_PATH)
    if not card_path.exists():
        raise FileNotFoundError(f"Agent card not found: {config.AGENT_CARD_PATH}")

    with card_path.open() as f:
        data = json.load(f)

    return AgentCard(**data)


AGENT_CARD = _load_agent_card()
