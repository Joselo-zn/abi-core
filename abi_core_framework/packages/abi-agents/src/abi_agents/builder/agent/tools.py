"""Builder Agent — Tools.

Real @agent.tool usage: ensures the ephemeral agent's model is present on the
shared Ollama host before a container is built for it. Wraps the
framework-level abi_core.common.model_tools (available to any agent, not
Builder-specific) with the DAG position this agent needs.
"""

from app import agent
from abi_core.common.utils import abi_logging
from abi_core.common.model_tools import find_model, pull_model


@agent.tool(
    name="ensure_model_available",
    depends_on=["generate_config"],
    input_map={"config": "$generate_config"},
)
async def ensure_model_available(config: dict) -> dict:
    """Ensure the ephemeral agent's model is pulled before the container is built.

    Looks up the model in the framework's {model: location} registry; if not
    found anywhere, pulls it to the default shared host. Errors propagate via
    the same `{"status": "error", ...}` passthrough already used by
    verify_tools/generate_config, so a missing/undownloadable model skips this
    task without crashing the rest of the plan.
    """
    if config.get("status") == "error":
        return config

    import os

    model = config.get("llm_config_override", {}).get("model") or os.getenv(
        "EPHEMERAL_MODEL_NAME", os.getenv("MODEL_NAME", "devstral:24b")
    )

    location = await find_model(model)
    if location:
        return {**config, "model_used": model, "model_location": location}

    abi_logging(f"[⬇️] Model '{model}' not found in registry, pulling...")
    try:
        async for progress in pull_model(model):
            status = progress.get("status", "")
            if status:
                abi_logging(f"[⬇️] '{model}': {status}")
    except Exception as e:
        return {
            "status": "error",
            "message": f"Model '{model}' could not be made available: {e}",
            "task_id": config.get("task_id"),
        }

    location = await find_model(model)
    if not location:
        return {
            "status": "error",
            "message": f"Model '{model}' pull completed but model still not found in registry",
            "task_id": config.get("task_id"),
        }
    return {**config, "model_used": model, "model_location": location}
