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
    tools=["write_file"],
)
async def analyze_and_execute(context, query):
    """Phase 2: LLM autonomous execution with tools, enriched with memory context."""
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.context_loader import build_execution_prompt

    # Inject memory context if AMS is available
    memory_context = ""
    if config.AGENT_MEMORY_URL and config.CONTEXT_ID:
        try:
            from agent_memory_client import MemoryAPIClient, MemoryClientConfig
            mem_client = MemoryAPIClient(MemoryClientConfig(base_url=config.AGENT_MEMORY_URL))
            prompt_data = await mem_client.memory_prompt(
                query=query,
                session_id=config.CONTEXT_ID,
                long_term_search={"text": query, "limit": 3},
            )
            # Extract context from memory messages
            for msg in prompt_data.get("messages", []):
                if msg.get("role") == "system" and msg.get("content"):
                    memory_context = msg["content"]
                    break
            if memory_context:
                abi_logging(f"[🧠] Memory context injected ({len(memory_context)} chars)")
        except Exception as e:
            abi_logging(f"[⚠️] Memory context unavailable: {e}")

    execution_prompt = build_execution_prompt(
        query=query,
        tools=ZOMBIE_TOOLS,
        artifacts=context.get("artifacts", []),
        workspace=config.WORKSPACE,
    )

    # Combine system prompt with memory context
    system_prompt = config.SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{config.SYSTEM_PROMPT}\n\n## Context from previous tasks:\n{memory_context}"

    result = await invoke(
        config.LLM_CONFIG, execution_prompt,
        tools=ZOMBIE_TOOLS, system_prompt=system_prompt,
        required_tools=["write_file"],
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

    # Persist result summary to working memory for subsequent tasks
    if config.AGENT_MEMORY_URL and config.CONTEXT_ID:
        try:
            from agent_memory_client import MemoryAPIClient, MemoryClientConfig
            from agent_memory_client.models import WorkingMemory

            mem_client = MemoryAPIClient(MemoryClientConfig(base_url=config.AGENT_MEMORY_URL))
            filenames = [a["filename"] for a in uploaded_artifacts] if uploaded_artifacts else []
            summary = (
                f"Agent '{config.AGENT_NAME}' completed task. "
                f"Result: {execution_result.get('result', '')[:200]}. "
                f"Files created: {filenames}"
            )
            await mem_client.put_working_memory(
                config.CONTEXT_ID,
                WorkingMemory(
                    session_id=config.CONTEXT_ID,
                    messages=[{"role": "assistant", "content": summary}],
                ),
            )
            abi_logging(f"[🧠] Stored result in working memory")
        except Exception as e:
            abi_logging(f"[⚠️] Could not store memory: {e}")

    return {
        "status": status,
        "result": execution_result.get("result", "") if status == "completed" else str(e),
        "uploaded_artifacts": uploaded_artifacts,
        "agent": config.AGENT_NAME,
    }
