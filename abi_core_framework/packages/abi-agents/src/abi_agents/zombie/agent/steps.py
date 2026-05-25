"""Zombie Agent — Steps.

DAG:
  gather_context → analyze_and_execute → synthesize_and_report
"""

from app import agent
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent.zombie import ZOMBIE_TOOLS
from abi_agents.zombie.agent.config.config import config


@agent.step(
    name="gather_context",
    input_map={"query": "$input.query"},
)
async def gather_context(query):
    """Phase 1: Pull specific artifacts from MinIO, prepare workspace."""
    from abi_core.common.context_loader import load_agent_context

    abi_logging(f"Loading context to start execution...")

    ctx = await load_agent_context(
        artifact_keys=config.ARTIFACT_KEYS if config.ARTIFACT_KEYS else None,
        workspace=config.WORKSPACE,
    )
    return {
        "query": query,
        "workspace": config.WORKSPACE,
        "artifacts": ctx["artifacts"],
        "tools_available": config.TOOL_NAMES,
        "system_prompt": config.SYSTEM_PROMPT,
    }


@agent.step(
    name="analyze_and_execute",
    input_map={"context": "$gather_context", "query": "$input.query"},
    depends_on=["gather_context"],
)
async def analyze_and_execute(context, query):
    """Phase 2: LLM autonomous execution with tools."""
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.context_loader import build_execution_prompt

    execution_prompt = build_execution_prompt(
        query=query,
        tools=ZOMBIE_TOOLS,
        artifacts=context.get("artifacts", []),
        workspace=config.WORKSPACE,
    )
    result = await invoke(
        config.LLM_CONFIG, execution_prompt,
        tools=ZOMBIE_TOOLS, system_prompt=config.SYSTEM_PROMPT,
    )
    
    abi_logging(f"[✅] Query: {query} Results: {result}")
    
    return {"result": result, "query": query}


@agent.step(
    name="synthesize_and_report",
    input_map={"execution_result": "$analyze_and_execute", "context": "$gather_context"},
    depends_on=["analyze_and_execute"],
)
async def synthesize_and_report(execution_result, context):
    """Phase 3: Upload generated artifacts and flush logs."""
    from abi_core.common.artifact_store import upload_workspace_artifacts

    uploaded_artifacts = []
    status = "completed"

    try:
        uploaded_artifacts = await upload_workspace_artifacts(
            agent_name=config.AGENT_NAME,
            workspace=config.WORKSPACE,
            exclude=context.get("artifacts", []),
        )
    except Exception as e:
        status = "incompleted"
        abi_logging(f"[❌] Error synthesize_and_report: {e}")

    return {
        "status": status,
        "result": execution_result.get("result", "") if status == "completed" else str(e),
        "uploaded_artifacts": uploaded_artifacts,
        "agent": config.AGENT_NAME,
    }
