"""Orchestrator Agent — Tools.

Real @agent.tool usage: read-only check of which model each ephemeral task
would use and where it lives, so the plan-confirmation summary can show the
user "installed" vs "will be downloaded" before anything is built. Wraps the
framework-level abi_core.common.model_tools (available to any agent).
"""

import os

from app import agent
from abi_core.common.model_tools import list_available_models


@agent.tool(
    name="check_model_availability",
    depends_on=["extract_plan"],
    input_map={"plan_result": "$extract_plan"},
)
async def check_model_availability(plan_result: dict) -> dict:
    """Read-only — never mutates anything, safe to run unconditionally.

    Unlike Builder's ensure_model_available (which may pull a model), this
    only reports {task_id: {"model": ..., "location": str | None}} for the
    plan-confirmation summary.
    """
    if not isinstance(plan_result, dict) or "plan" not in plan_result:
        return plan_result  # passthrough: gate_passthrough/clarification/error

    default_model = os.getenv("EPHEMERAL_MODEL_NAME", os.getenv("MODEL_NAME", "devstral:24b"))
    plan = plan_result.get("plan") or {}
    registry = await list_available_models()

    model_status = {}
    for t in plan.get("tasks", []):
        if t.get("type") not in ("build_and_execute", "create_tools_and_execute"):
            continue
        model = t.get("builder_spec", {}).get("llm_config", {}).get("model", default_model)
        model_status[t["task_id"]] = {
            "model": model,
            "location": registry.get(model),
        }

    return {"model_status": model_status}
