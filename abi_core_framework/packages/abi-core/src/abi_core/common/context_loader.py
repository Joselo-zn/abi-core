"""
Context Loader — Dynamic injection and revocation of tools and artifacts.

Principle: Least privilege applied to tools. An agent receives only what
it needs for a specific task, uses it, and gives it back.

Usage:
    from abi_core.common.context_loader import load_agent_context, load_agent_context_sync

    # Async (inside async code)
    ctx = await load_agent_context(
        mcp_tool_names=["query_sales_db"],
        library_tool_names=["ShellTool"],
        artifact_keys=["task_1/data.json"],
    )

    # Sync (at init time, outside event loop)
    ctx = load_agent_context_sync(
        library_tool_names=["write_file", "read_file"],
    )
"""

import asyncio
import os
import shutil
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging


def load_agent_context_sync(**kwargs) -> Dict[str, Any]:
    """Synchronous wrapper for load_agent_context.

    Safe to call at module/class init time when no event loop is running.
    Accepts the same arguments as load_agent_context.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(load_agent_context(**kwargs))
    finally:
        loop.close()


async def load_agent_context(
    mcp_tool_names: Optional[List[str]] = None,
    library_tool_names: Optional[List[str]] = None,
    artifact_keys: Optional[List[str]] = None,
    workspace: str = "/app/workspace",
    ephemeral: bool = False,
) -> Dict[str, Any]:
    """Load dynamic context for any agent.

    Resolves MCP tools, library tools, and downloads artifacts.
    Each agent decides how to use the returned context.

    Args:
        mcp_tool_names: MCP tool names to resolve via MCPToolkit.
        library_tool_names: Library tool names to import dynamically.
        artifact_keys: MinIO keys to download to workspace.
        workspace: Local directory for artifacts.
        ephemeral: Mark tools as one-time use (metadata flag).

    Returns:
        {
            "mcp_tools": [LangChain tools from MCP],
            "lib_tools": [LangChain tools from libraries],
            "artifacts": [local file paths],
            "ephemeral": bool,
        }
    """
    result = {
        "mcp_tools": [],
        "lib_tools": [],
        "artifacts": [],
        "ephemeral": ephemeral,
    }

    os.makedirs(workspace, exist_ok=True)

    # ── MCP Tools ──────────────────────────────────────────────
    if mcp_tool_names:
        try:
            from langchain_core.tools import StructuredTool
            from abi_core.common.semantic_tools import MCPToolkit

            toolkit = MCPToolkit()
            for name in mcp_tool_names:
                async def _call_mcp(tool_name=name, **kwargs):
                    return await toolkit.call(tool_name, **kwargs)

                result["mcp_tools"].append(StructuredTool.from_function(
                    coroutine=_call_mcp,
                    name=name,
                    description=f"MCP tool: {name}",
                ))
            abi_logging(f"[🔧] Loaded {len(result['mcp_tools'])} MCP tools: {mcp_tool_names}")
        except Exception as e:
            abi_logging(f"[⚠️] Failed to load MCP tools: {e}")

    # ── Library Tools ──────────────────────────────────────────
    if library_tool_names:
        try:
            from abi_core.common.library_tools import zombie_tools, BASE_TOOLS

            # Map tool names to base tools
            base_by_name = {t.name: t for t in BASE_TOOLS}
            for name in library_tool_names:
                if name in base_by_name:
                    result["lib_tools"].append(base_by_name[name])
                else:
                    abi_logging(f"[⚠️] Library tool '{name}' not found")
                    
        except Exception as e:
            abi_logging(f"[⚠️] Failed to load library tools: {e}")

    # ── Artifacts ──────────────────────────────────────────────
    if artifact_keys:
        try:
            from abi_core.common.artifact_store import download_artifacts
            result["artifacts"] = await download_artifacts(
                keys=artifact_keys,
                workspace=workspace,
            )
        except Exception as e:
            abi_logging(f"[⚠️] Failed to download artifacts: {e}")

    return result


async def unload_agent_context(
    agent: Any = None,
    tool_names: Optional[List[str]] = None,
    cleanup_artifacts: bool = False,
    workspace: str = "/app/workspace",
) -> None:
    """Revoke tools and clean up artifacts from an agent.

    Args:
        agent: AbiAgent instance to remove tools from.
        tool_names: Names of tools to revoke.
        cleanup_artifacts: If True, delete all files in workspace.
        workspace: Directory to clean up.
    """
    # ── Revoke tools ───────────────────────────────────────────
    if agent and tool_names and hasattr(agent, "tools"):
        names_set = set(tool_names)
        before = len(agent.tools)
        agent.tools = [t for t in agent.tools if t.name not in names_set]
        removed = before - len(agent.tools)
        if removed:
            abi_logging(f"[🔒] Revoked {removed} tools from {agent.agent_name}: {tool_names}")

    # ── Clean up artifacts ─────────────────────────────────────
    if cleanup_artifacts and os.path.exists(workspace):
        try:
            for f in os.listdir(workspace):
                path = os.path.join(workspace, f)
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            abi_logging(f"[🧹] Cleaned workspace: {workspace}")
        except Exception as e:
            abi_logging(f"[⚠️] Failed to clean workspace: {e}")


def build_execution_prompt(
    query: str,
    tools: Optional[List] = None,
    artifacts: Optional[List[str]] = None,
    workspace: str = "/app/workspace",
) -> str:
    """Build a dynamic execution prompt from query, tools, and artifacts.

    Generates a clean prompt that describes the task, lists available tools
    with their descriptions, and includes artifact paths if present.

    Args:
        query: The task description.
        tools: LangChain tools (each with .name and .description).
        artifacts: Local file paths of downloaded artifacts.
        workspace: Workspace directory path.

    Returns:
        Formatted prompt string ready for LLM.
    """
    parts = [f"Task: {query}"]

    if tools:
        tools_desc = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        parts.append(f"\nAvailable tools:\n{tools_desc}")

    if artifacts:
        arts = "\n".join(f"  - {p}" for p in artifacts)
        parts.append(f"\nArtifacts in workspace ({workspace}):\n{arts}")

    return "\n".join(parts)


async def self_deregister(agent_name: str, destroy: bool = True) -> None:
    """Self-deregister from semantic layer and optionally exit the process.

    Called by ephemeral agents at the end of their task to clean up
    their own registration. Each agent is responsible for its own lifecycle.

    Args:
        agent_name: The agent's name (used to find the card in Weaviate).
        destroy: If True, exit the process after deregistering (container stops).
    """
    abi_logging(f"[🔄] Self-deregister starting for '{agent_name}'")

    # Step 1: Flush logs before anything else
    try:
        from abi_core.common.utils import flush_logs
        await flush_logs(agent_name=agent_name)
        abi_logging(f"[📋] Logs flushed for '{agent_name}'")
    except Exception as e:
        abi_logging(f"[⚠️] Log flush failed for '{agent_name}': {e}")

    # Step 2: Deregister from semantic layer (ephemeral-safe tool)
    try:
        from abi_core.common.semantic_tools import MCPToolkit
        toolkit = MCPToolkit()
        result = await toolkit.call("self_deregister_ephemeral", agent_name=agent_name)
        if isinstance(result, dict) and result.get("success"):
            abi_logging(f"[🗑️] Self-deregistered '{agent_name}' from semantic layer")
        else:
            error = result.get("error", "unknown") if isinstance(result, dict) else str(result)
            abi_logging(f"[⚠️] Deregister response for '{agent_name}': {error}")
    except Exception as e:
        abi_logging(f"[⚠️] Self-deregister failed for '{agent_name}': {e}")

    # Step 3: Graceful shutdown — stop uvicorn then exit
    if destroy:
        abi_logging(f"[💀] Agent '{agent_name}' shutting down")
        import asyncio
        await asyncio.sleep(0.5)
        import os
        os._exit(0)
