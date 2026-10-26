"""
Ephemeral configuration — everything that is the same for every ephemeral
the Builder launches: image, network, start-up timeout, LLM settings, the
swarm's service endpoints, and the start command.

build_container (steps.py) only adds what belongs to each task (name, port,
system prompt, tools, artifacts, card, ids, role).

The ephemeral installs the same abi-core-ai version the Builder runs, so the
Builder and its ephemerals never run different versions; the image
(agentbase/abi-image-v2) carries only abi-core's base libraries.
Spec: .abi/specs/not-implemented/ephemeral-abi-core-version-pin.md

Read from the environment on every call, not at import.
"""

import json
import os
from importlib.metadata import version

# Provider SDKs are optional extras of abi-core-ai named after the provider;
# the ephemeral image only has Ollama's.
_PROVIDER_EXTRAS = {"gemini", "openai", "anthropic", "grok", "bedrock", "vertex"}

# Where the zombie lives once abi-core-ai is installed in the ephemeral.
_ZOMBIE_PKG = "abi_agents/zombie/agent"
_SITE_PACKAGES = "/opt/venv/lib/python3.12/site-packages"


def image() -> str:
    return os.getenv("ABI_IMAGE", "agentbase/abi-image-v2:latest")


def network() -> str:
    return os.getenv("DOCKER_NETWORK", "abi_network")


def health_timeout() -> int:
    # Generous on purpose: the start-up pip install alone took 69s live
    # (2026-10-05) and a 60s budget aborted a healthy ephemeral. The wait
    # ends early if the container dies (check_container_health), so a broken
    # start-up still fails fast.
    return int(os.getenv("EPHEMERAL_HEALTH_TIMEOUT", "300"))


def provider() -> str:
    """Ephemerals can run on a different LLM provider than the Builder itself
    (e.g. Ollama for the swarm, Gemini for ephemerals). `or`, not a getenv
    default: compose passes an unset var as ""."""
    return (os.getenv("EPHEMERAL_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "ollama").strip().lower()


def abi_core_version() -> str:
    """The abi-core-ai version this Builder runs: its ephemerals install the
    same one."""
    return version("abi-core-ai")


def start_command(eph_provider: str) -> str:
    """Installs this Builder's abi-core-ai version (with the provider's
    extra), copies the zombie from it and starts it."""
    extra = f"[{eph_provider}]" if eph_provider in _PROVIDER_EXTRAS else ""
    return (
        f"pip install --quiet --no-cache-dir 'abi-core-ai{extra}=={abi_core_version()}' && "
        f"cp -r {_SITE_PACKAGES}/{_ZOMBIE_PKG}/* /app/ && "
        f"python3 main.py"
    )


def llm_params_env(eph_provider: str, override: dict) -> dict:
    """The ephemeral's LLM_EXTRA_PARAMS / LLM_TEMPERATURE.

    EPHEMERAL_LLM_EXTRA_PARAMS (a JSON object) first; without it, the
    Builder's own LLM_EXTRA_PARAMS only when the ephemeral runs on the same
    provider — the parameters are provider-specific. The task's
    builder_spec["llm_config"] goes on top: its extra_params win, and its
    temperature becomes LLM_TEMPERATURE. Invalid JSON raises ValueError.
    See .abi/specs/implemented/llm-params-from-config.md."""
    from abi_core.agent.llm_provider import parse_extra_params

    builder_provider = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
    if os.getenv("EPHEMERAL_LLM_EXTRA_PARAMS"):
        params = parse_extra_params(os.getenv("EPHEMERAL_LLM_EXTRA_PARAMS"), "EPHEMERAL_LLM_EXTRA_PARAMS")
    elif eph_provider == builder_provider:
        params = parse_extra_params(os.getenv("LLM_EXTRA_PARAMS"))
    else:
        params = {}

    task_params = override.get("extra_params") or {}
    if not isinstance(task_params, dict):
        raise ValueError(f"builder_spec llm_config.extra_params must be an object, got {type(task_params).__name__}")
    params = {**params, **task_params}

    env = {"LLM_EXTRA_PARAMS": json.dumps(params)} if params else {}
    if override.get("temperature") is not None:
        env["LLM_TEMPERATURE"] = str(float(override["temperature"]))
    return env


def llm_env(eph_provider: str, override: dict) -> dict:
    """Provider, credentials and parameters of the ephemeral's LLM."""
    env = {"LLM_PROVIDER": eph_provider}
    if eph_provider != "ollama":
        # Hosted provider: the ephemeral needs the key (and an endpoint only
        # if one is set). Accepted risk while ephemerals still have run_shell
        # and network: use a dedicated, rate-limited key for ephemerals.
        env["LLM_API_KEY"] = os.getenv("EPHEMERAL_LLM_API_KEY") or os.getenv("LLM_API_KEY", "")
        if os.getenv("EPHEMERAL_LLM_BASE_URL"):
            env["LLM_BASE_URL"] = os.getenv("EPHEMERAL_LLM_BASE_URL")
    env.update(llm_params_env(eph_provider, override))
    return env


def base_env(eph_provider: str, override: dict) -> dict:
    """Every environment variable that is the same for all ephemerals."""
    return {
        "ZOMBIE_MODE": "active",
        "AGENT_HOST": "0.0.0.0",
        "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        **llm_env(eph_provider, override),
        "MCP_HOST": os.getenv("MCP_HOST", "localhost"),
        "MCP_PORT": os.getenv("MCP_PORT", "10100"),
        "MCP_TRANSPORT": os.getenv("MCP_TRANSPORT", "streamable-http"),
        "SEMANTIC_LAYER_HOST": os.getenv("SEMANTIC_LAYER_HOST", ""),
        # The A2A validator checks every outgoing call against Guardian/OPA.
        # Without these it went to localhost and, in strict mode, denied
        # every call an ephemeral made (send_link, the reviewer's
        # questions) — live 2026-10-09. Ephemerals only received calls
        # before the reviewer pipeline.
        **{k: os.environ[k] for k in ("OPA_URL", "GUARDIAN_URL") if os.environ.get(k)},
        "ARTIFACT_ENDPOINT": os.getenv("ARTIFACT_ENDPOINT", ""),
        "ARTIFACT_ACCESS_KEY": os.getenv("ARTIFACT_ACCESS_KEY", ""),
        "ARTIFACT_SECRET_KEY": os.getenv("ARTIFACT_SECRET_KEY", ""),
        "ARTIFACT_BUCKET": os.getenv("ARTIFACT_BUCKET", "abi-artifacts"),
        "LOG_TO_ARTIFACT_STORE": os.getenv("LOG_TO_ARTIFACT_STORE", "true"),
        "LOG_BUCKET": os.getenv("LOG_BUCKET", "abi-logs"),
        # Same session backend the Orchestrator writes process_context and
        # inter-task contracts to. Without these the ephemeral fell back to
        # an in-memory backend — its reads of PLAN_CONTEXT_ID / dependency
        # contracts always came back empty, and the contract it wrote on
        # completion died with the container. Confirmed live 2026-10-03.
        # See .abi/fixes/2026-10-03-cross-file-integration-context.md.
        "SESSION_BACKEND": os.getenv("SESSION_BACKEND", "memory"),
        "SESSION_REDIS_URL": os.getenv("SESSION_REDIS_URL", os.getenv("REDIS_URL", "")),
        "AGENT_MEMORY_URL": os.getenv("AGENT_MEMORY_URL", "http://abi-swarm-agent-memory:8000"),
        "SERVICE_MODULE": "",
        "SERVICE_COMMAND": start_command(eph_provider),
        "PYTHONPATH": "/app",
    }
