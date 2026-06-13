"""Zombie Agent Configuration — reads all config from environment variables."""

import json
import os

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentInterface


class ZombieConfig:
    """Centralized configuration for the zombie agent."""

    # Agent Identity
    ZOMBIE_MODE: str = os.getenv("ZOMBIE_MODE", "idle")
    AGENT_NAME: str = os.getenv("AGENT_NAME", "zombie")
    AGENT_PORT: int = int(os.getenv("AGENT_PORT", "11440"))
    AGENT_DISPLAY_NAME: str = AGENT_NAME
    AGENT_DESCRIPTION: str = f"Ephemeral agent: {AGENT_NAME}"

    # Task
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "You are a generic ABI agent.")
    WORKSPACE: str = "/app/workspace"

    # Tools (JSON list of MCP tool names)
    _TOOLS_JSON: str = os.getenv("TOOLS", "[]")
    try:
        TOOL_NAMES: list = json.loads(_TOOLS_JSON)
    except json.JSONDecodeError:
        TOOL_NAMES: list = []

    # Artifacts (JSON list of MinIO keys to download)
    _ARTIFACT_KEYS_JSON: str = os.getenv("ARTIFACT_KEYS", "[]")
    try:
        ARTIFACT_KEYS: list = json.loads(_ARTIFACT_KEYS_JSON)
    except json.JSONDecodeError:
        ARTIFACT_KEYS: list = []

    # Library tools (JSON list injected by builder)
    _LIB_TOOLS_JSON: str = os.getenv("LIBRARY_TOOLS", "[]")
    try:
        LIBRARY_TOOL_NAMES: list = json.loads(_LIB_TOOLS_JSON)
    except json.JSONDecodeError:
        LIBRARY_TOOL_NAMES: list = []

    # LLM
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen2.5:3b")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_CONFIG: dict = {
        "provider": LLM_PROVIDER,
        "model": MODEL_NAME,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
        "base_url": os.getenv("LLM_BASE_URL", OLLAMA_HOST),
        "api_key": os.getenv("LLM_API_KEY", ""),
    }

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_ARTIFACT_STORE: bool = os.getenv("LOG_TO_ARTIFACT_STORE", "true").lower() == "true"
    LOG_AGENT_NAME: str = os.getenv("LOG_AGENT_NAME", AGENT_NAME)
    LOG_BUCKET: str = os.getenv("LOG_BUCKET", "abi-logs")

    # Agent Memory (Redis AMS)
    CONTEXT_ID: str = os.getenv("CONTEXT_ID", "")
    AGENT_MEMORY_URL: str = os.getenv("AGENT_MEMORY_URL", "")

    # Agent Card — write to disk from AGENT_CARD_JSON env var for MCP auth
    AGENT_CARD: str = "ephemeral"
    _AGENT_CARD_PATH: str = "/tmp/agent_card.json"
    _agent_card_json: str = os.getenv("AGENT_CARD_JSON", "")
    if _agent_card_json:
        try:
            with open(_AGENT_CARD_PATH, "w") as f:
                f.write(_agent_card_json)
            os.environ["AGENT_CARD"] = _AGENT_CARD_PATH
        except Exception:
            pass

    @classmethod
    def build_agent_card(cls) -> AgentCard:
        """Build A2A AgentCard from config."""
        return AgentCard(
            name=cls.AGENT_NAME,
            description=cls.AGENT_DESCRIPTION,
            version="1.0.0",
            capabilities=AgentCapabilities(
                streaming=True,
                push_notifications=False,
            ),
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            supported_interfaces=[
                AgentInterface(url=f"http://{cls.AGENT_NAME}:{cls.AGENT_PORT}", protocol_binding="JSONRPC")
            ],
            skills=[AgentSkill(
                id="execute_task",
                name=f"Execute ({cls.AGENT_NAME})",
                description=cls.SYSTEM_PROMPT[:200],
                tags=cls.TOOL_NAMES or ["general"],
            )],
        )


config = ZombieConfig()
