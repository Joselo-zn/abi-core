"""Planner Agent — Steps.

DAG: analyze_query → parse_plan → assign_agents
"""

import json

from app import agent
from abi_core.common.utils import abi_logging, clean_llm_json
from abi_core.common.plan_models import PlannerOutput
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent
from abi_core.common.agent_card_loader import get_agent_url


@agent.step(
    name="analyze_query",
    input_map={
        "query": "$input.query",
        "context": "$input.context",
    },
)
async def analyze_query(query, context):
    """Prepare the planning prompt from query + context."""
    planning_query = f"User request: {query}\nContext: {json.dumps(context, indent=2)}"
    return {"planning_query": planning_query}


@agent.step(
    name="parse_plan",
    depends_on=["analyze_query"],
    input_map={"raw_response": "$input.llm_response"},
)
def parse_plan(raw_response):
    """Clean, parse, and validate the LLM response into a structured plan."""
    if not raw_response:
        return {"status": "error", "message": "Empty LLM response"}

    parsed = clean_llm_json(raw_response)

    try:
        validated = PlannerOutput.model_validate(parsed)
        plan_dict = validated.to_dict()
        abi_logging(f"[✅] Plan validated by PlannerOutput schema")
        plan = plan_dict.get("plan", {})
        abi_logging(f"[📋] PLAN: objective='{plan.get('objective', '')}' strategy={plan.get('execution_strategy', '')}")
        for t in plan.get("tasks", []):
            abi_logging(f"[📋]   {t.get('task_id')}: {t.get('description', '')[:120]} deps={t.get('dependencies', [])}")
        plan_dict = _enforce_atomic_tasks(plan_dict)
        return plan_dict
    except Exception as e:
        abi_logging(f"[⚠️] Pydantic validation failed, using raw parsed: {e}")
        from abi_core.common.utils import _clean_description
        plan = parsed.get("plan", {})
        for task in plan.get("tasks", []):
            if "description" in task:
                task["description"] = _clean_description(task["description"])
        parsed = _enforce_atomic_tasks(parsed)
        return parsed


def _enforce_atomic_tasks(plan_data: dict) -> dict:
    """Defensive validation: truncate to 5 tasks, ensure targets exist."""
    plan = plan_data.get("plan", {})
    tasks = plan.get("tasks", [])

    # Max 5 tasks
    if len(tasks) > 5:
        abi_logging(f"[⚠️] Plan has {len(tasks)} tasks, truncating to 5")
        plan["tasks"] = tasks[:5]
        tasks = plan["tasks"]

    # Ensure each task has a target
    for task in tasks:
        if not task.get("target") or not task["target"].get("tag"):
            # Try to infer filename from description
            desc = task.get("description", "")
            tag = _infer_filename(desc)
            task["target"] = {"tag": tag, "type": "file"}
            abi_logging(f"[🔧] Inferred target for {task.get('task_id', '?')}: {tag}")

    return plan_data


def _infer_filename(description: str) -> str:
    """Try to extract a filename from a task description."""
    import re
    # Match patterns like "named X.py" or "file X.sh"
    match = re.search(r'named\s+(\S+\.\w+)', description, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'file\s+(\S+\.\w+)', description, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback: use task description words
    words = description.split()[:3]
    return "_".join(w.lower() for w in words if w.isalnum()) + ".py"


@agent.step(
    name="assign_agents",
    depends_on=["parse_plan"],
    input_map={"plan_data": "$parse_plan"},
)
async def assign_agents(plan_data):
    """Assign agents to each task in the plan."""
    if plan_data.get("status") != "ready":
        return plan_data

    plan = plan_data.get("plan", {})
    tasks = plan.get("tasks", [])

    INFRA_AGENTS = {"builder", "planner", "orchestrator", "guardian", "semantic-layer"}

    abi_logging(f"[🔍] Assigning agents to {len(tasks)} tasks...")

    for task in tasks:
        task_desc = task.get("description", "")
        task_id = task.get("task_id", "unknown")

        found_agent = await tool_find_agent.ainvoke(task_desc)

        if found_agent:
            agent_name = (
                found_agent.name if hasattr(found_agent, "name") else
                found_agent.get("name", "") if isinstance(found_agent, dict) else ""
            ).lower()
            if any(infra in agent_name for infra in INFRA_AGENTS):
                abi_logging(f"[⚠️] Task '{task_id}': found '{agent_name}' but it's infrastructure, skipping")
                found_agent = None

        if found_agent:
            # Verify agent is actually reachable before assigning
            agent_url = get_agent_url(found_agent) if hasattr(found_agent, "supported_interfaces") else ""
            if not agent_url and isinstance(found_agent, dict):
                agent_url = found_agent.get("url", "")

            if agent_url:
                agent_name_str = (
                    found_agent.name if hasattr(found_agent, "name") else
                    found_agent.get("name", "unknown") if isinstance(found_agent, dict) else "unknown"
                )
                health = await AbiAgent.check_health(agent_url, agent_name_str)
                if health.get("status") not in ("healthy",):
                    abi_logging(
                        f"[⚠️] Task '{task_id}': agent '{agent_name_str}' found but unavailable "
                        f"({health.get('status')}), falling back to build_and_execute"
                    )
                    found_agent = None

        if found_agent:
            if hasattr(found_agent, "model_dump"):
                agent_data = found_agent.model_dump()
            elif hasattr(found_agent, "DESCRIPTOR"):
                # Protobuf AgentCard — convert to dict
                from google.protobuf.json_format import MessageToDict
                agent_data = MessageToDict(found_agent)
            elif isinstance(found_agent, dict):
                agent_data = found_agent
            else:
                agent_data = {"name": str(found_agent)}
            task["type"] = "execute"
            task["agents"] = [agent_data]
            abi_logging(f"[✅] Task '{task_id}': agent found and healthy → execute")
            continue

        task["type"] = "build_and_execute"
        task["agents"] = []
        task["builder_spec"] = {
            "system_prompt": task_desc,
            "ephemeral": True,
        }
        abi_logging(f"[🏗️] Task '{task_id}': no agent → build_and_execute (builder resolves tools)")

    abi_logging(f"[📋] FINAL PLAN ({len(tasks)} tasks):")
    for t in tasks:
        tid = t.get("task_id", "?")
        ttype = t.get("type", "?")
        desc = t.get("description", "")[:100]
        agents = [a.get("name", "?") if isinstance(a, dict) else str(a) for a in t.get("agents", [])]
        abi_logging(f"[📋]   {tid} [{ttype}] {desc} agents={agents}")

    return plan_data
