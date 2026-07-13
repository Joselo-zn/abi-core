"""
abi_core.session — Framework-level session management (LB/multi-pod safe).

Opt-in capability: an opaque, backend-generated token maps to an internal
``context_id`` plus the conversation context for that context_id. State lives in
a pluggable backend (in-memory for dev, Redis for multi-pod), never in per-pod
process RAM.

    from abi_core.session import SessionStore, session_backend_from_env

    store = SessionStore.from_env()          # picks backend from env
    session = await store.create_session()    # opaque token + context_id
    ctx = await store.get_context(session.context_id)

See ``abi_core.session.store`` for details and WORKING_RULES →
"Perspectiva Local vs Global".
"""

from abi_core.session.store import (
    Session,
    SessionBackend,
    InMemorySessionBackend,
    RedisSessionBackend,
    SessionStore,
    session_backend_from_env,
)

__all__ = [
    "Session",
    "SessionBackend",
    "InMemorySessionBackend",
    "RedisSessionBackend",
    "SessionStore",
    "session_backend_from_env",
]
