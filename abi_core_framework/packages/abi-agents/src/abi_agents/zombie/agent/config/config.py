"""Zombie Agent Configuration — reads all config from environment variables."""

import json
import os

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentInterface
from abi_core.agent.llm_provider import llm_config_from_env


class ZombieConfig:
    """Centralized configuration for the zombie agent."""

    # Agent Identity
    ZOMBIE_MODE: str = os.getenv("ZOMBIE_MODE", "idle")
    # "code" (default) or "reviewer" — same zombie, another set of tasks
    # (ephemeral-reviewer-pipeline 02.3). RUN_ID: the plan run a reviewer
    # belongs to; its project folder is projects/<RUN_ID>/.
    ZOMBIE_ROLE: str = os.getenv("ZOMBIE_ROLE", "code").strip().lower()
    RUN_ID: str = os.getenv("RUN_ID", "")
    AGENT_NAME: str = os.getenv("AGENT_NAME", "zombie")
    AGENT_PORT: int = int(os.getenv("AGENT_PORT", "11440"))
    AGENT_DISPLAY_NAME: str = AGENT_NAME
    AGENT_DESCRIPTION: str = f"Ephemeral agent: {AGENT_NAME}"

    # Task
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "You are a generic ABI agent.")
    WORKSPACE: str = "/app/workspace"

    # Backstop for the analyze_and_execute step — NOT the mechanism that
    # decides "this is taking too long" anymore (that's wrong: a flat
    # wall-clock cap killed genuinely-progressing work under concurrent
    # Ollama load, confirmed live 2026-09-30, 5 parallel tasks all cut at
    # exactly 600s while still producing real chunks). The real bounding now
    # happens at the point of actual work — call_timeout=120.0 per LLM
    # stream chunk (llm_provider.py) and a 30s timeout on the AMS memory
    # call (memory/operations.py) — both inactivity-based, not duration-
    # based. 3600s is a last-resort net for something genuinely infinite
    # that neither of those catches (e.g. a tool-calling loop that never
    # converges), not a budget for normal work. See .abi/specs/
    # not-implemented/analyze-and-execute-inactivity-vs-wallclock-timeout.md.
    EXECUTION_TIMEOUT: float = float(os.getenv("EXECUTION_TIMEOUT", "3600"))

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
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3:latest")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    # LLM settings from the environment (LLM_PROVIDER, MODEL_NAME, LLM_BASE_URL,
    # LLM_API_KEY, LLM_TEMPERATURE, LLM_EXTRA_PARAMS — a JSON object passed
    # as-is to the LangChain model). See abi_core.agent.llm_provider.
    # reasoning=False on Ollama: qwen3's thinking mode ON hit EXECUTION_TIMEOUT
    # (600s) on analyze_and_execute — see
    # .abi/tsd/2026-09-09-routing-decision-model-profiling.md. LLM_EXTRA_PARAMS
    # overrides it.
    LLM_CONFIG: dict = llm_config_from_env(ollama_extra_params={"reasoning": False})

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_ARTIFACT_STORE: bool = os.getenv("LOG_TO_ARTIFACT_STORE", "true").lower() == "true"
    LOG_AGENT_NAME: str = os.getenv("LOG_AGENT_NAME", AGENT_NAME)
    LOG_BUCKET: str = os.getenv("LOG_BUCKET", "abi-logs")

    # Agent Memory (Redis AMS)
    CONTEXT_ID: str = os.getenv("CONTEXT_ID", "")
    AGENT_MEMORY_URL: str = os.getenv("AGENT_MEMORY_URL", "")

    # process-awareness.md (Tier 3) — the plan-wide id (distinct from
    # CONTEXT_ID, this task's own id), used to read back the process_context
    # blob the Orchestrator wrote via session_backend for the whole plan.
    PLAN_CONTEXT_ID: str = os.getenv("PLAN_CONTEXT_ID", "")

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
