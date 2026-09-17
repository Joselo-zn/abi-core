"""
abi_core.memory.tools — LangChain tools for LLM-driven memory read/write.

    from abi_core.memory import MEMORY_TOOLS
    # add to an agent's tool list, e.g. tools = [*MEMORY_TOOLS, ...]

The tools are async. `context_id` resolution prefers the *current graph
invocation's* runtime context (set via `context=` on `.astream()`/`.ainvoke()`,
readable anywhere during that run via `langgraph.runtime.get_runtime()`) over
the `CONTEXT_ID` env var. This matters for concurrency: these tools were unused
anywhere in the codebase until the 2026-08 Orchestrator tool-call-routing
redesign started binding them — resolving `context_id` purely from an env var
would have been process-wide shared state, silently mixing up sessions under
concurrent requests in one async server (never triggered before precisely
*because* nothing used them). `get_runtime()` is per-invocation via
contextvars, safe for concurrent use; the env var stays as a fallback for
callers outside a LangGraph run.
"""

from typing import Optional

from langchain_core.tools import tool as langchain_tool

from abi_core.memory.operations import (
    add_long_term_memory as _add_long_term_memory,
    add_short_term_memory as _add_short_term_memory,
    get_long_term_memory as _get_long_term_memory,
    get_short_term_memory as _get_short_term_memory,
)


def _resolve_context_id() -> Optional[str]:
    """Prefer the context_id of the current graph invocation over the env
    var — see module docstring. Returns None if there's no active graph run
    (operations.py's functions then fall back to the CONTEXT_ID env var)."""
    try:
        from langgraph.runtime import get_runtime

        ctx = get_runtime().context or {}
        if ctx.get("context_id"):
            return ctx["context_id"]
    except Exception:
        pass
    return None


@langchain_tool
async def get_long_term_memory(query: str) -> str:
    """Search long-term memory for information relevant to a query.

    Use this to recall facts, past results, decisions, or preferences from
    previous sessions.

    Args:
        query: What to look for (natural language).

    Returns:
        Matching memory entries as text, or an empty string if none found.
    """
    result = await _get_long_term_memory(query, context_id=_resolve_context_id())
    return result or "(no relevant long-term memory found)"


@langchain_tool
async def get_short_term_memory() -> str:
    """Retrieve the current session's working memory (recent context).

    Use this to recall what has happened so far in the current task/session.

    Returns:
        The session's working-memory text, or an empty string if none.
    """
    result = await _get_short_term_memory(context_id=_resolve_context_id())
    return result or "(no working memory for this session)"


@langchain_tool
async def save_short_term_memory(content: str, topic: str = "agent_note") -> str:
    """Save something worth remembering for the REST OF THIS SESSION ONLY —
    e.g. a preference the user just stated, an intermediate decision. Use
    save_long_term_memory instead for anything that should survive beyond
    this session.

    Args:
        content: The text to remember.
        topic: A short label for what this is about.

    Returns:
        "saved" on success, or an explanation if it couldn't be saved.
    """
    cid = _resolve_context_id()
    ok = await _add_short_term_memory(
        topic=topic, task=cid or "session", content=content, context_id=cid
    )
    return "saved" if ok else "could not save (memory unavailable)"


@langchain_tool
async def save_long_term_memory(content: str, topic: str = "agent_note") -> str:
    """Save something worth remembering BEYOND this session — a durable fact,
    decision, or user preference that should be recalled in future sessions
    too. Use save_short_term_memory instead for anything only relevant to the
    rest of this conversation.

    Args:
        content: The text to remember.
        topic: A short label for what this is about.

    Returns:
        "saved" on success, or an explanation if it couldn't be saved.
    """
    cid = _resolve_context_id()
    ok = await _add_long_term_memory(
        topic=topic, task=cid or "session", content=content, context_id=cid
    )
    return "saved" if ok else "could not save (memory unavailable)"


MEMORY_TOOLS = [get_long_term_memory, get_short_term_memory, save_short_term_memory, save_long_term_memory]
