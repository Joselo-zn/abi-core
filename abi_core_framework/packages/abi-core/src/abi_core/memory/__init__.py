"""
abi_core.memory — Built-in short/long-term memory for ABI agents.

Backed by the Redis Agent Memory Server (AMS), this module provides
system-wide memory that any agent can use:

Write (inside @agent.step / @agent.task):
    from abi_core.memory import add_short_term_memory, add_long_term_memory
    await add_short_term_memory(topic, task, content, context_id=...)
    await add_long_term_memory(topic, task, content, context_id=...)

Read (helpers or LLM tools):
    from abi_core.memory import get_short_term_memory, get_long_term_memory
    from abi_core.memory import recall_memory_context  # hydrate a prompt
    from abi_core.memory import MEMORY_TOOLS           # LangChain tools

All operations degrade gracefully when the AMS is unavailable.
"""

from abi_core.memory.client import (
    get_memory_client,
    resolve_context_id,
    resolve_memory_url,
)
from abi_core.memory.operations import (
    add_long_term_memory,
    add_short_term_memory,
    get_long_term_memory,
    get_short_term_memory,
    recall_memory_context,
)
from abi_core.memory.tools import MEMORY_TOOLS

__all__ = [
    "add_short_term_memory",
    "add_long_term_memory",
    "get_short_term_memory",
    "get_long_term_memory",
    "recall_memory_context",
    "MEMORY_TOOLS",
    "get_memory_client",
    "resolve_context_id",
    "resolve_memory_url",
]
