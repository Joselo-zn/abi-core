"""
abi_core.common.async_task_store — Status store for `@agent.task_async` /
`@agent.task_schedule`, plus their structured audit-log helper.

A scheduled firing is, conceptually, a `task_async` run that fires itself —
both decorators share one store. Pluggable backend, mirroring
`abi_core.session.store.SessionBackend` exactly (see
.abi/tsd/2026-08-02-async-task-store-backend-pluggable.md for why: the
"Local vs Global" architecture principle in WORKING_RULES.md means state
that must survive a pod — which a background/scheduled task's status is the
clearest case of — belongs in system memory (Redis), never process RAM only).

Backends:
- ``InMemoryAsyncTaskBackend`` — default; per-process dict. Fine for dev / a
  single pod. State does NOT survive a restart or cross pods.
- ``RedisAsyncTaskBackend`` — shared state in Redis (``redis.asyncio``). Any
  pod sees the same "is this job already running" answer — required for
  ``overlap_policy="skip"`` to actually prevent overlap across replicas.

Environment variables (consumed by ``async_task_backend_from_env``):
    ASYNC_TASK_BACKEND   "memory" (default) | "redis"
    REDIS_URL            Redis URL for the redis backend (same var used by
                          RedisSessionBackend / the Agent Memory Server)
"""

from __future__ import annotations

import os
import json
import time
import uuid
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from abi_core.common.utils import abi_logging

_DEFAULT_MAX_RECORDS = 500


@dataclass
class AsyncTaskRecord:
    """Status of a single `task_async`/`task_schedule` run."""

    async_task_id: str
    name: str
    status: str = "running"  # "running" | "done" | "failed"
    context_id: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None
    result: Any = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AsyncTaskRecord":
        return cls(
            async_task_id=data["async_task_id"],
            name=data["name"],
            status=data.get("status", "running"),
            context_id=data.get("context_id"),
            attempts=int(data.get("attempts", 0)),
            error=data.get("error"),
            result=data.get("result"),
            started_at=float(data.get("started_at", time.time())),
            finished_at=data.get("finished_at"),
        )


# ── Backend interface ───────────────────────────────────────────

class AsyncTaskBackend(ABC):
    """Pluggable storage for task_async/task_schedule run status.

    Same contract shape as `abi_core.session.store.SessionBackend` —
    deliberate, not a parallel invention. All methods are async for a
    uniform interface across in-memory and Redis backends.
    """

    @abstractmethod
    async def create(self, async_task_id: str, name: str, context_id: Optional[str]) -> AsyncTaskRecord: ...

    @abstractmethod
    async def is_running(self, name: str) -> bool: ...

    @abstractmethod
    async def mark_done(self, async_task_id: str, result: Any) -> None: ...

    @abstractmethod
    async def mark_failed(self, async_task_id: str, error: str) -> None: ...

    @abstractmethod
    async def get(self, async_task_id: str) -> Optional[AsyncTaskRecord]: ...

    @abstractmethod
    async def bump_attempts(self, async_task_id: str, attempts: int) -> None: ...


# ── In-memory backend (default) ─────────────────────────────────

class InMemoryAsyncTaskBackend(AsyncTaskBackend):
    """Per-process, dict-based backend.

    Suitable for development or a single-pod agent. State does not survive a
    restart and is NOT shared across pods — a `task_schedule` job with
    `overlap_policy="skip"` only prevents overlap within THIS process. Use
    `RedisAsyncTaskBackend` for a multi-replica deployment.
    """

    def __init__(self, max_records: int = _DEFAULT_MAX_RECORDS):
        self._records: "OrderedDict[str, AsyncTaskRecord]" = OrderedDict()
        self._max_records = max_records

    def _evict_if_needed(self) -> None:
        # FIFO eviction of the oldest COMPLETED records only — never evict a
        # still-"running" record, that would silently break overlap checks.
        if len(self._records) <= self._max_records:
            return
        for async_task_id, record in list(self._records.items()):
            if len(self._records) <= self._max_records:
                break
            if record.status != "running":
                self._records.pop(async_task_id, None)

    async def create(self, async_task_id: str, name: str, context_id: Optional[str]) -> AsyncTaskRecord:
        record = AsyncTaskRecord(async_task_id=async_task_id, name=name, context_id=context_id)
        self._records[async_task_id] = record
        self._evict_if_needed()
        return record

    async def is_running(self, name: str) -> bool:
        return any(r.status == "running" and r.name == name for r in self._records.values())

    async def mark_done(self, async_task_id: str, result: Any) -> None:
        record = self._records.get(async_task_id)
        if record is None:
            return
        record.status = "done"
        record.result = result
        record.finished_at = time.time()

    async def mark_failed(self, async_task_id: str, error: str) -> None:
        record = self._records.get(async_task_id)
        if record is None:
            return
        record.status = "failed"
        record.error = error
        record.finished_at = time.time()

    async def get(self, async_task_id: str) -> Optional[AsyncTaskRecord]:
        record = self._records.get(async_task_id)
        return AsyncTaskRecord.from_dict(record.to_dict()) if record else None

    async def bump_attempts(self, async_task_id: str, attempts: int) -> None:
        record = self._records.get(async_task_id)
        if record is not None:
            record.attempts = attempts


# ── Redis backend (multi-pod / LB-safe) ─────────────────────────

class RedisAsyncTaskBackend(AsyncTaskBackend):
    """Shared-state backend on Redis via ``redis.asyncio``.

    Any pod/replica sees the same "is this job already running" answer —
    required for `overlap_policy="skip"` to actually prevent overlap across
    replicas. Reuses the same REDIS_URL the Agent Memory Server / session
    store use — no new infrastructure to provision.

    Keys:
        {ns}:task:{async_task_id}     JSON blob of the AsyncTaskRecord
        {ns}:running:{name}           Set of async_task_ids currently running
                                       for this job name (for is_running()).

    A record has no TTL by default (retained until the process explicitly
    marks it done/failed and the caller reads it); this mirrors the
    in-memory backend's "keep completed records around for inspection"
    behavior rather than the session store's TTL-based expiry, since task
    status is meant to be queried after the fact, not treated as ephemeral
    session state.
    """

    def __init__(self, redis_url: str, namespace: str = "abi"):
        self.redis_url = redis_url
        self.namespace = namespace
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                abi_logging(
                    "[⚠️] redis not installed — async task status disabled",
                    level="warning",
                )
                return None
            self._client = aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._client

    def _tk(self, async_task_id: str) -> str:
        return f"{self.namespace}:task:{async_task_id}"

    def _rk(self, name: str) -> str:
        return f"{self.namespace}:running:{name}"

    async def create(self, async_task_id: str, name: str, context_id: Optional[str]) -> AsyncTaskRecord:
        record = AsyncTaskRecord(async_task_id=async_task_id, name=name, context_id=context_id)
        client = self._get_client()
        if client is None:
            return record
        try:
            async with client.pipeline(transaction=True) as pipe:
                pipe.set(self._tk(async_task_id), json.dumps(record.to_dict()))
                pipe.sadd(self._rk(name), async_task_id)
                await pipe.execute()
        except Exception as e:  # noqa: BLE001 — never block task execution on the store
            abi_logging(f"[⚠️] Could not persist async task record to Redis: {e}", level="warning")
        return record

    async def is_running(self, name: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            running_ids = await client.smembers(self._rk(name))
            return len(running_ids) > 0
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not check async task overlap: {e}", level="warning")
            return False

    async def _save(self, record: AsyncTaskRecord) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            await client.set(self._tk(record.async_task_id), json.dumps(record.to_dict()))
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not update async task record: {e}", level="warning")

    async def mark_done(self, async_task_id: str, result: Any) -> None:
        record = await self.get(async_task_id)
        if record is None:
            return
        record.status = "done"
        record.result = result
        record.finished_at = time.time()
        await self._save(record)
        client = self._get_client()
        if client is not None:
            try:
                await client.srem(self._rk(record.name), async_task_id)
            except Exception as e:  # noqa: BLE001
                abi_logging(f"[⚠️] Could not clear running marker: {e}", level="warning")

    async def mark_failed(self, async_task_id: str, error: str) -> None:
        record = await self.get(async_task_id)
        if record is None:
            return
        record.status = "failed"
        record.error = error
        record.finished_at = time.time()
        await self._save(record)
        client = self._get_client()
        if client is not None:
            try:
                await client.srem(self._rk(record.name), async_task_id)
            except Exception as e:  # noqa: BLE001
                abi_logging(f"[⚠️] Could not clear running marker: {e}", level="warning")

    async def get(self, async_task_id: str) -> Optional[AsyncTaskRecord]:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(self._tk(async_task_id))
            if not raw:
                return None
            return AsyncTaskRecord.from_dict(json.loads(raw))
        except Exception as e:  # noqa: BLE001
            abi_logging(f"[⚠️] Could not read async task record: {e}", level="warning")
            return None

    async def bump_attempts(self, async_task_id: str, attempts: int) -> None:
        record = await self.get(async_task_id)
        if record is None:
            return
        record.attempts = attempts
        await self._save(record)


def async_task_backend_from_env() -> AsyncTaskBackend:
    """Build an async-task backend from environment variables.

    ``ASYNC_TASK_BACKEND=redis`` selects Redis (using ``REDIS_URL``, falling
    back to ``redis://localhost:6379/0``); anything else (default) selects
    the in-memory backend.
    """
    backend = os.getenv("ASYNC_TASK_BACKEND", "memory").strip().lower()

    if backend == "redis":
        redis_url = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        abi_logging(f"[⏱️] Async task backend: redis ({redis_url})")
        return RedisAsyncTaskBackend(redis_url)

    abi_logging("[⏱️] Async task backend: in-memory (per-pod; not LB-safe)")
    return InMemoryAsyncTaskBackend()


# ── Structured audit logging ─────────────────────────────────────

def log_task_event(
    event: str,
    *,
    task_name: str,
    async_task_id: str,
    attempt: int = 0,
    max_retries: int = 0,
    status: str = "",
    error: Optional[str] = None,
    context_id: Optional[str] = None,
) -> None:
    """Structured JSON audit record for a task_async/task_schedule event.

    Goes through the existing `abi_logging` → stdout (+ MinIO buffer if
    LOG_TO_ARTIFACT_STORE=true) pipeline — no new persistence layer. Prefixed
    for grep-ability; level="error" on failure events so it's easy to filter.
    """
    payload = {
        "event": event,
        "task_name": task_name,
        "async_task_id": async_task_id,
        "attempt": attempt,
        "max_retries": max_retries,
        "status": status,
        "error": error,
        "context_id": context_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    level = "error" if status == "failed" or event.endswith("_failure") else "info"
    abi_logging(f"[TASK_ASYNC_AUDIT] {json.dumps(payload)}", level=level)


def new_async_task_id() -> str:
    """Short, prefixed id — distinct from A2A task_ids, easy to grep in logs."""
    return f"atask-{uuid.uuid4().hex[:12]}"
