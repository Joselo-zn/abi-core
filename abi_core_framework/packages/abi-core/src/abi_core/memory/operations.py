"""
abi_core.memory.operations — Built-in short/long-term memory operations.

These are the public, imperative memory functions for use inside
``@agent.step`` / ``@agent.task`` functions:

    from abi_core.agent import add_short_term_memory, add_long_term_memory

    await add_short_term_memory("pending_clarification", context_id, content)
    await add_long_term_memory("plan_execution", objective, content)

Design rules:
- ``context_id`` and ``memory_url`` are optional; they fall back to the
  ``CONTEXT_ID`` / ``AGENT_MEMORY_URL`` environment variables.
- ``topic`` maps to the AMS record ``topics`` list; ``task`` maps to ``entities``.
- All functions degrade gracefully: on any failure (AMS down, library missing)
  they log a warning and return ``False`` / ``""`` instead of raising, so a
  memory failure never blocks agent execution (local vs global resilience).
"""

from datetime import datetime, timezone
from typing import Optional

from abi_core.common.utils import abi_logging
from abi_core.memory.client import get_memory_client, resolve_context_id


async def add_short_term_memory(
    topic: str,
    task: str,
    content: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
) -> bool:
    """Store a short-term (working) memory record for a session.

    Working memory is session-scoped (by ``context_id``) and represents the
    current task context — e.g. a pending clarification or intermediate state.

    Args:
        topic: A topic label (stored under the record's ``topics``).
        task: The task/entity this memory is about (stored under ``entities``).
        content: The memory text.
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.

    Returns:
        ``True`` if stored, ``False`` if memory is unavailable or the call failed.
    """
    sid = resolve_context_id(context_id)
    client = get_memory_client(memory_url)
    if client is None or not sid:
        return False

    try:
        from agent_memory_client.models import ClientMemoryRecord

        record = ClientMemoryRecord(
            text=content,
            topics=[topic] if topic else None,
            entities=[task] if task else None,
            memory_type="message",
            session_id=sid,
        )
        await client.add_memories_to_working_memory(session_id=sid, memories=[record])
        abi_logging(f"[🧠] Short-term memory stored (topic='{topic}', session='{sid}')")
        return True
    except Exception as e:  # noqa: BLE001 — memory must never block execution
        abi_logging(f"[⚠️] Could not store short-term memory: {e}", level="warning")
        return False


async def add_long_term_memory(
    topic: str,
    task: str,
    content: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
) -> bool:
    """Store a long-term (semantic) memory record, persisted and searchable.

    Long-term memory survives across sessions and is retrieved by semantic
    similarity — e.g. past plans, results, preferences.

    Args:
        topic: A topic label (stored under the record's ``topics``).
        task: The task/entity this memory is about (stored under ``entities``).
        content: The memory text.
        context_id: Session id, stored for traceability. Falls back to ``CONTEXT_ID``.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.

    Returns:
        ``True`` if stored, ``False`` if memory is unavailable or the call failed.
    """
    client = get_memory_client(memory_url)
    if client is None:
        return False

    try:
        from agent_memory_client.models import ClientMemoryRecord

        sid = resolve_context_id(context_id)
        record = ClientMemoryRecord(
            text=content,
            topics=[topic] if topic else None,
            entities=[task] if task else None,
            memory_type="semantic",
            session_id=sid or None,
        )
        await client.create_long_term_memory([record])
        abi_logging(f"[🧠] Long-term memory stored (topic='{topic}')")
        return True
    except Exception as e:  # noqa: BLE001 — memory must never block execution
        abi_logging(f"[⚠️] Could not store long-term memory: {e}", level="warning")
        return False


async def get_short_term_memory(
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
) -> str:
    """Retrieve the working-memory messages for a session as plain text.

    Args:
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.

    Returns:
        Newline-joined memory text, or ``""`` if none / unavailable.
    """
    sid = resolve_context_id(context_id)
    client = get_memory_client(memory_url)
    if client is None or not sid:
        return ""

    try:
        _created, memory = await client.get_or_create_working_memory(session_id=sid)
        if memory is None:
            return ""

        lines = []
        for msg in getattr(memory, "messages", []) or []:
            text = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if text:
                lines.append(text)
        for rec in getattr(memory, "memories", []) or []:
            text = rec.get("text") if isinstance(rec, dict) else getattr(rec, "text", None)
            if text:
                lines.append(text)
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] Could not read short-term memory: {e}", level="warning")
        return ""


async def get_long_term_memory(
    query: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Semantic search over long-term memory; returns matching texts.

    Args:
        query: Natural-language query for semantic search.
        context_id: Optional session filter. Falls back to ``CONTEXT_ID``.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.
        limit: Max number of results.

    Returns:
        Newline-joined memory texts, or ``""`` if none / unavailable.
    """
    client = get_memory_client(memory_url)
    if client is None or not query:
        return ""

    try:
        results = await client.search_long_term_memory(text=query, limit=limit)
        memories = getattr(results, "memories", None) or []
        texts = []
        for m in memories:
            text = m.get("text") if isinstance(m, dict) else getattr(m, "text", None)
            if text:
                texts.append(text)
        return "\n".join(texts)
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] Could not search long-term memory: {e}", level="warning")
        return ""


async def recall_memory_context(
    query: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
    long_term_limit: int = 3,
) -> str:
    """Hydrate a query with relevant memory and return injectable context text.

    Combines session (short-term) and long-term memory via the AMS
    ``memory_prompt`` endpoint. Intended to be prepended to an agent's system
    prompt before calling the LLM.

    Args:
        query: The user/task query to find relevant context for.
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.
        long_term_limit: Max long-term memories to include.

    Returns:
        Context text suitable for injection, or ``""`` if none / unavailable.
    """
    sid = resolve_context_id(context_id)
    client = get_memory_client(memory_url)
    if client is None or not sid:
        return ""

    try:
        prompt_data = await client.memory_prompt(
            query=query,
            session_id=sid,
            long_term_search={"text": query, "limit": long_term_limit},
        )
        for msg in prompt_data.get("messages", []):
            if msg.get("role") == "system" and msg.get("content"):
                return msg["content"]
        return ""
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] Memory context unavailable: {e}", level="warning")
        return ""


# ── Session state (key/value flags in working memory `data`) ────────

async def set_session_state(
    key: str,
    value,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
) -> bool:
    """Set a key/value flag in the session's working-memory data.

    Unlike ``add_short_term_memory`` (which appends a message), this stores a
    structured, overwritable value — suitable for system events that must be
    read and later cleared, e.g. a pending clarification.

    Args:
        key: The data key (e.g. ``"pending_clarification"``).
        value: Any JSON-serializable value.
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.

    Returns:
        ``True`` if stored, ``False`` if memory is unavailable or the call failed.
    """
    sid = resolve_context_id(context_id)
    client = get_memory_client(memory_url)
    if client is None or not sid:
        return False

    try:
        await client.update_working_memory_data(
            session_id=sid,
            data_updates={key: value},
            merge_strategy="merge",
        )
        abi_logging(f"[🧠] Session state set: '{key}' (session='{sid}')")
        return True
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] Could not set session state '{key}': {e}", level="warning")
        return False


async def get_session_state(
    key: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
    default=None,
):
    """Read a key/value flag from the session's working-memory data.

    Args:
        key: The data key to read.
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.
        default: Value to return when the key is absent or memory is unavailable.

    Returns:
        The stored value, or ``default``.
    """
    sid = resolve_context_id(context_id)
    client = get_memory_client(memory_url)
    if client is None or not sid:
        return default

    try:
        _created, memory = await client.get_or_create_working_memory(session_id=sid)
        if memory is None:
            return default
        data = getattr(memory, "data", None) or {}
        return data.get(key, default)
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] Could not read session state '{key}': {e}", level="warning")
        return default


async def clear_session_state(
    key: str,
    context_id: Optional[str] = None,
    memory_url: Optional[str] = None,
) -> bool:
    """Clear a key/value flag from the session's working-memory data.

    Args:
        key: The data key to clear (set to ``None``).
        context_id: Session id. Falls back to ``CONTEXT_ID`` env var.
        memory_url: AMS base URL. Falls back to ``AGENT_MEMORY_URL`` env var.

    Returns:
        ``True`` if cleared, ``False`` if memory is unavailable or the call failed.
    """
    return await set_session_state(key, None, context_id=context_id, memory_url=memory_url)
