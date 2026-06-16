"""
abi_core.memory.client — Lazy construction of the Agent Memory Server client.

The Agent Memory Server (AMS) provides system-wide short-term (working) and
long-term (semantic) memory, shared across the swarm over the Docker network.

This module builds a ``MemoryAPIClient`` from explicit arguments or environment
variables, and degrades gracefully (returns ``None``) when the AMS is not
configured or the client library is unavailable — so memory is always optional
and never blocks agent execution.

Environment variables:
    AGENT_MEMORY_URL  Base URL of the AMS (e.g. http://abi-swarm-agent-memory:8000)
    CONTEXT_ID        Default session/context id used as the AMS session_id
"""

import os
from typing import Optional

from abi_core.common.utils import abi_logging


def resolve_memory_url(memory_url: Optional[str] = None) -> str:
    """Return the AMS base URL from the argument or AGENT_MEMORY_URL env var."""
    return memory_url or os.getenv("AGENT_MEMORY_URL", "")


def resolve_context_id(context_id: Optional[str] = None) -> str:
    """Return the session/context id from the argument or CONTEXT_ID env var."""
    return context_id or os.getenv("CONTEXT_ID", "")


def get_memory_client(memory_url: Optional[str] = None):
    """Build a ``MemoryAPIClient`` or return ``None`` if memory is unavailable.

    The client library is imported lazily so agents that don't use memory
    don't pay an import cost and don't fail if the dependency is missing.

    Args:
        memory_url: Override the AMS base URL. Falls back to ``AGENT_MEMORY_URL``.

    Returns:
        A configured ``MemoryAPIClient`` instance, or ``None`` when the AMS URL
        is not set or the ``agent-memory-client`` package is not installed.
    """
    url = resolve_memory_url(memory_url)
    if not url:
        return None

    try:
        from agent_memory_client import MemoryAPIClient, MemoryClientConfig

        return MemoryAPIClient(MemoryClientConfig(base_url=url))
    except ImportError:
        abi_logging(
            "[⚠️] agent-memory-client not installed — memory features disabled",
            level="warning",
        )
        return None
    except Exception as e:  # noqa: BLE001 — defensive: never block on memory init
        abi_logging(f"[⚠️] Could not initialize memory client: {e}", level="warning")
        return None
