"""
abi_core.session.store — Framework-level session management (LB/multi-pod safe).

A session ties an opaque, backend-generated token to an internal ``context_id``
plus the accumulated conversation context for that context_id. It is a *generic*
capability: any agent built on abi-core can opt in, regardless of whether it uses
the reference orchestrator/swarm.

Two concerns, one pluggable backend:

1. **Tokens** — ``create_session`` → opaque token (``secrets.token_hex``); the id
   is generated in the *backend*, never by the client (prevents spoofing and the
   shared ``web-session`` collision). ``resolve`` / ``rotate`` / ``destroy``.
2. **Conversation context** — ``get_context`` / ``update_context`` /
   ``clear_context`` keyed by ``context_id``. This replaces the per-process
   in-memory ``_conversation_history`` that broke under load balancers.

Backends:
- ``InMemorySessionBackend`` — default; per-process dict. Fine for dev / a single
  pod. State does NOT survive a restart or cross pods.
- ``RedisSessionBackend`` — shared state in Redis (``redis.asyncio``). Any pod
  resolves the same token/context → multi-turn works behind a load balancer.

Design rules (see WORKING_RULES → "Perspectiva Local vs Global"):
- State that must survive a pod/agent lives in the *system* memory (Redis), never
  in process RAM.
- All ops are ``async`` — the whole agent pipeline is async, so the Redis backend
  awaits I/O without blocking the event loop, and the in-memory backend is a
  near-free ``async`` over a dict. Uniform interface: ``AbiAgent`` never needs to
  know which backend is underneath.
- Graceful degradation: a backend failure logs a warning and returns a safe
  default (``None`` / ``{}``) instead of raising, so a session-store hiccup never
  crashes agent execution.

Environment variables (consumed by ``session_backend_from_env``):
    SESSION_BACKEND    "memory" (default) | "redis"
    SESSION_TTL        Session/context lifetime in seconds (default 3600)
    SESSION_REDIS_URL  Redis URL for the redis backend (falls back to REDIS_URL,
                       then redis://localhost:6379/0)
"""

from __future__ import annotations

import os
import json
import time
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging

_DEFAULT_TTL = 3600  # 1 hour
_TOKEN_BYTES = 32     # secrets.token_hex(32) → 64 hex chars
_TOKEN_PREFIX = "abi_sess_"


# ── Session model ───────────────────────────────────────────────

@dataclass
class Session:
    """An active session: opaque token(s) → internal ``context_id``."""

    session_id: str
    context_id: str
    tokens: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return self.expires_at > 0 and now >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            context_id=data["context_id"],
            tokens=list(data.get("tokens", [])),
            created_at=float(data.get("created_at", time.time())),
            expires_at=float(data.get("expires_at", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )


def _new_token() -> str:
    return f"{_TOKEN_PREFIX}{secrets.token_hex(_TOKEN_BYTES)}"


# ── Backend interface ───────────────────────────────────────────

class SessionBackend(ABC):
    """Pluggable storage for sessions and conversation context.

    All methods are ``async`` for a uniform interface across in-memory and
    Redis backends. Implementations should degrade gracefully (log + safe
    default) rather than raise, so the session store never blocks an agent.
    """

    def __init__(self, ttl: int = _DEFAULT_TTL):
        self.ttl = ttl

    # -- token lifecycle --
    @abstractmethod
    async def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> Session: ...

    @abstractmethod
    async def resolve(self, token: str) -> Optional[Session]: ...

    @abstractmethod
    async def rotate(self, token: str) -> Optional[str]: ...

    @abstractmethod
    async def destroy(self, token: str) -> bool: ...

    # -- conversation context (keyed by context_id) --
    @abstractmethod
    async def get_context(self, context_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def update_context(self, context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    async def clear_context(self, context_id: str) -> None: ...


# ── In-memory backend (default) ─────────────────────────────────

class InMemorySessionBackend(SessionBackend):
    """Per-process, dict-based backend.

    Suitable for development or a single-pod agent. State does not survive a
    restart and is NOT shared across pods — use ``RedisSessionBackend`` behind
    a load balancer.
    """

    def __init__(self, ttl: int = _DEFAULT_TTL):
        super().__init__(ttl)
        self._sessions: Dict[str, Session] = {}   # session_id → Session
        self._tokens: Dict[str, str] = {}         # token → session_id
        self._contexts: Dict[str, Dict[str, Any]] = {}  # context_id → context

    async def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> Session:
        session_id = secrets.token_hex(16)
        context_id = secrets.token_hex(16)
        token = _new_token()
        now = time.time()
        session = Session(
            session_id=session_id,
            context_id=context_id,
            tokens=[token],
            created_at=now,
            expires_at=now + self.ttl if self.ttl else 0.0,
            metadata=metadata or {},
        )
        # Store a copy so external mutations of the returned Session (or later
        # internal mutations) never alias the caller's object — matches the
        # Redis backend, which always returns fresh objects from JSON.
        self._sessions[session_id] = Session.from_dict(session.to_dict())
        self._tokens[token] = session_id
        abi_logging(f"[🔑] Session created (context={context_id[:8]}…)")
        return session

    async def resolve(self, token: str) -> Optional[Session]:
        session_id = self._tokens.get(token)
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            await self._destroy_session(session)
            return None
        return Session.from_dict(session.to_dict())

    async def rotate(self, token: str) -> Optional[str]:
        session_id = self._tokens.get(token)
        stored = self._sessions.get(session_id) if session_id else None
        if stored is None or stored.is_expired():
            return None
        new_token = _new_token()
        self._tokens.pop(token, None)
        if token in stored.tokens:
            stored.tokens.remove(token)
        stored.tokens.append(new_token)
        self._tokens[new_token] = stored.session_id
        return new_token

    async def destroy(self, token: str) -> bool:
        session = await self.resolve(token)
        if session is None:
            return False
        await self._destroy_session(session)
        return True

    async def _destroy_session(self, session: Session) -> None:
        for t in session.tokens:
            self._tokens.pop(t, None)
        self._sessions.pop(session.session_id, None)
        self._contexts.pop(session.context_id, None)

    async def get_context(self, context_id: str) -> Dict[str, Any]:
        return dict(self._contexts.get(context_id, {}))

    async def update_context(self, context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self._contexts.setdefault(context_id, {})
        ctx.update(patch)
        return dict(ctx)

    async def clear_context(self, context_id: str) -> None:
        self._contexts.pop(context_id, None)


# ── Redis backend (multi-pod / LB-safe) ─────────────────────────

class RedisSessionBackend(SessionBackend):
    """Shared-state backend on Redis via ``redis.asyncio``.

    Any pod resolves the same token → context from the shared store, so a
    multi-turn conversation survives across pods behind a load balancer.

    Keys:
        {ns}:session:{session_id}   Hash-free JSON blob of the Session
        {ns}:token:{token}          → session_id (string)
        {ns}:context:{context_id}   Hash of context fields (JSON-encoded values)

    All keys carry the TTL, refreshed on write. Concurrency: context writes use
    per-field ``HSET`` so concurrent updates to *different* keys don't clobber
    each other; a true read-modify-write on the *same* field is last-writer-wins
    (documented limitation — good enough for turn-scoped state).
    """

    def __init__(
        self,
        redis_url: str,
        ttl: int = _DEFAULT_TTL,
        namespace: str = "abi",
    ):
        super().__init__(ttl)
        self.redis_url = redis_url
        self.namespace = namespace
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                abi_logging(
                    "[⚠️] redis not installed — session state disabled",
                    level="warning",
                )
                return None
            self._client = aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._client

    def _sk(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}"

    def _tk(self, token: str) -> str:
        return f"{self.namespace}:token:{token}"

    def _ck(self, context_id: str) -> str:
        return f"{self.namespace}:context:{context_id}"

    async def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> Session:
        client = self._get_client()
        session_id = secrets.token_hex(16)
        context_id = secrets.token_hex(16)
        token = _new_token()
        now = time.time()
        session = Session(
            session_id=session_id,
            context_id=context_id,
            tokens=[token],
            created_at=now,
            expires_at=now + self.ttl if self.ttl else 0.0,
            metadata=metadata or {},
        )
        if client is None:
            return session
        try:
            async with client.pipeline(transaction=True) as pipe:
                pipe.set(self._sk(session_id), json.dumps(session.to_dict()))
                pipe.set(self._tk(token), session_id)
                if self.ttl:
                    pipe.expire(self._sk(session_id), self.ttl)
                    pipe.expire(self._tk(token), self.ttl)
                await pipe.execute()
            abi_logging(f"[🔑] Session created in Redis (context={context_id[:8]}…)")
        except Exception as e:  # noqa: BLE001 — never block on session store
            abi_logging(f"[⚠️] Could not persist session to Redis: {e}", level="warning")
        return session

    async def _load_session(self, session_id: str) -> Optional[Session]:
        client = self._get_client()
        if client is None:
            return None
        raw = await client.get(self._sk(session_id))
        if not raw:
            return None
        try:
            return Session.from_dict(json.loads(raw))
        except (ValueError, KeyError):
            return None

    async def resolve(self, token: str) -> Optional[Session]:
        client = self._get_client()
        if client is None:
            return None
        try:
            session_id = await client.get(self._tk(token))
            if not session_id:
                return None
            session = await self._load_session(session_id)
            if session is None:
                return None
            if session.is_expired():
                await self._destroy_session(session)
                return None
            return session
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not resolve session token: {e}", level="warning")
            return None

    async def _save_session(self, session: Session) -> None:
        client = self._get_client()
        if client is None:
            return
        await client.set(self._sk(session.session_id), json.dumps(session.to_dict()))
        if self.ttl:
            await client.expire(self._sk(session.session_id), self.ttl)

    async def rotate(self, token: str) -> Optional[str]:
        client = self._get_client()
        if client is None:
            return None
        session = await self.resolve(token)
        if session is None:
            return None
        new_token = _new_token()
        try:
            if token in session.tokens:
                session.tokens.remove(token)
            session.tokens.append(new_token)
            async with client.pipeline(transaction=True) as pipe:
                pipe.delete(self._tk(token))
                pipe.set(self._tk(new_token), session.session_id)
                pipe.set(self._sk(session.session_id), json.dumps(session.to_dict()))
                if self.ttl:
                    pipe.expire(self._tk(new_token), self.ttl)
                    pipe.expire(self._sk(session.session_id), self.ttl)
                await pipe.execute()
            return new_token
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not rotate session token: {e}", level="warning")
            return None

    async def destroy(self, token: str) -> bool:
        session = await self.resolve(token)
        if session is None:
            return False
        await self._destroy_session(session)
        return True

    async def _destroy_session(self, session: Session) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            keys = [self._tk(t) for t in session.tokens]
            keys.append(self._sk(session.session_id))
            keys.append(self._ck(session.context_id))
            if keys:
                await client.delete(*keys)
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not destroy session: {e}", level="warning")

    async def get_context(self, context_id: str) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {}
        try:
            raw = await client.hgetall(self._ck(context_id))
            if not raw:
                return {}
            out: Dict[str, Any] = {}
            for k, v in raw.items():
                try:
                    out[k] = json.loads(v)
                except (ValueError, TypeError):
                    out[k] = v
            return out
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not read session context: {e}", level="warning")
            return {}

    async def update_context(self, context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return dict(patch)
        try:
            mapping = {k: json.dumps(v) for k, v in patch.items()}
            key = self._ck(context_id)
            if mapping:
                await client.hset(key, mapping=mapping)
                if self.ttl:
                    await client.expire(key, self.ttl)
            return await self.get_context(context_id)
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not update session context: {e}", level="warning")
            return {}

    async def clear_context(self, context_id: str) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            await client.delete(self._ck(context_id))
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not clear session context: {e}", level="warning")


# ── Facade + factory ────────────────────────────────────────────

class SessionStore:
    """Thin facade over a :class:`SessionBackend`.

    Agents and web interfaces use this instead of touching a backend directly.
    Construct with an explicit backend, or use :func:`session_backend_from_env`
    /:meth:`from_env` to pick the backend from environment variables.
    """

    def __init__(self, backend: Optional[SessionBackend] = None):
        self.backend = backend or InMemorySessionBackend()

    @classmethod
    def from_env(cls) -> "SessionStore":
        return cls(session_backend_from_env())

    # token lifecycle
    async def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> Session:
        return await self.backend.create_session(metadata)

    async def resolve(self, token: str) -> Optional[Session]:
        return await self.backend.resolve(token)

    async def rotate(self, token: str) -> Optional[str]:
        return await self.backend.rotate(token)

    async def destroy(self, token: str) -> bool:
        return await self.backend.destroy(token)

    # conversation context
    async def get_context(self, context_id: str) -> Dict[str, Any]:
        return await self.backend.get_context(context_id)

    async def update_context(self, context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        return await self.backend.update_context(context_id, patch)

    async def clear_context(self, context_id: str) -> None:
        await self.backend.clear_context(context_id)


def session_backend_from_env() -> SessionBackend:
    """Build a session backend from environment variables.

    ``SESSION_BACKEND=redis`` selects Redis (using ``SESSION_REDIS_URL`` →
    ``REDIS_URL`` → ``redis://localhost:6379/0``); anything else (default)
    selects the in-memory backend.
    """
    ttl = int(os.getenv("SESSION_TTL", str(_DEFAULT_TTL)))
    backend = os.getenv("SESSION_BACKEND", "memory").strip().lower()

    if backend == "redis":
        redis_url = (
            os.getenv("SESSION_REDIS_URL")
            or os.getenv("REDIS_URL")
            or "redis://localhost:6379/0"
        )
        abi_logging(f"[🔑] Session backend: redis ({redis_url})")
        return RedisSessionBackend(redis_url, ttl=ttl)

    abi_logging("[🔑] Session backend: in-memory (per-pod; not LB-safe)")
    return InMemorySessionBackend(ttl=ttl)
