"""
abi_core.memory.tools — LangChain tools for LLM-driven memory retrieval.

These wrap the read operations so an LLM can recall memory on demand:

    from abi_core.memory import MEMORY_TOOLS
    # add to an agent's tool list, e.g. tools = [*MEMORY_TOOLS, ...]

The tools are async; they resolve ``context_id`` and the AMS URL from the
``CONTEXT_ID`` / ``AGENT_MEMORY_URL`` environment variables, so the LLM only
needs to supply a query (or nothing, for short-term recall).
"""

from langchain_core.tools import tool as langchain_tool

from abi_core.memory.operations import (
    get_long_term_memory as _get_long_term_memory,
    get_short_term_memory as _get_short_term_memory,
)


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
    result = await _get_long_term_memory(query)
    return result or "(no relevant long-term memory found)"


@langchain_tool
async def get_short_term_memory() -> str:
    """Retrieve the current session's working memory (recent context).

    Use this to recall what has happened so far in the current task/session.

    Returns:
        The session's working-memory text, or an empty string if none.
    """
    result = await _get_short_term_memory()
    return result or "(no working memory for this session)"


MEMORY_TOOLS = [get_long_term_memory, get_short_term_memory]
