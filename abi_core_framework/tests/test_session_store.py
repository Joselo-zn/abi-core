"""
Session store (abi_core.session.store): tokens → context_id and the
conversation context, on both backends. The swarm runs the Redis one
(SESSION_BACKEND=redis); its tests need a Redis at TEST_REDIS_URL and are
skipped without it (CI provides one).
Plan: .abi/specs/not-implemented/testing-plan.md (step 4).
"""

import os
import uuid

import pytest

import abi_core.session.store as store
from abi_core.session.store import (
    InMemorySessionBackend,
    RedisSessionBackend,
    SessionStore,
    session_backend_from_env,
)

REDIS_URL = os.getenv("TEST_REDIS_URL")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL not set")


def _redis_backend(ttl=60):
    # A namespace per test: tests never see each other's keys.
    return RedisSessionBackend(REDIS_URL, ttl=ttl, namespace=f"abi-test-{uuid.uuid4().hex[:8]}")


@pytest.fixture(params=["memory", pytest.param("redis", marks=needs_redis)])
def backend(request):
    return InMemorySessionBackend(ttl=60) if request.param == "memory" else _redis_backend()


# ── Contract: both backends behave the same ─────────────────────────────

@pytest.mark.asyncio
async def test_token_resolves_to_its_context(backend):
    session = await backend.create_session({"user": "u1"})
    assert session.tokens[0].startswith("abi_sess_")
    resolved = await backend.resolve(session.tokens[0])
    assert resolved.context_id == session.context_id
    assert resolved.metadata == {"user": "u1"}


@pytest.mark.asyncio
async def test_unknown_token_resolves_to_nothing(backend):
    assert await backend.resolve("abi_sess_not-a-token") is None


@pytest.mark.asyncio
async def test_sessions_get_distinct_contexts(backend):
    a = await backend.create_session()
    b = await backend.create_session()
    assert a.context_id != b.context_id and a.tokens != b.tokens


@pytest.mark.asyncio
async def test_rotate_invalidates_the_old_token(backend):
    session = await backend.create_session()
    old = session.tokens[0]
    new = await backend.rotate(old)
    assert new and new != old
    assert await backend.resolve(old) is None
    assert (await backend.resolve(new)).context_id == session.context_id


@pytest.mark.asyncio
async def test_rotate_unknown_token(backend):
    assert await backend.rotate("abi_sess_not-a-token") is None


@pytest.mark.asyncio
async def test_destroy_removes_token_and_context(backend):
    session = await backend.create_session()
    await backend.update_context(session.context_id, {"pending_plan": {"tasks": []}})
    assert await backend.destroy(session.tokens[0]) is True
    assert await backend.resolve(session.tokens[0]) is None
    assert await backend.get_context(session.context_id) == {}
    assert await backend.destroy(session.tokens[0]) is False


@pytest.mark.asyncio
async def test_context_updates_merge_and_round_trip(backend):
    ctx_id = (await backend.create_session()).context_id
    plan = {"tasks": [{"task_id": "t1", "dependencies": []}]}
    await backend.update_context(ctx_id, {"pending_plan": plan, "pending_plan_query": "snake"})
    merged = await backend.update_context(ctx_id, {"pending_plan_query": None, "turns": 3})
    assert merged == {"pending_plan": plan, "pending_plan_query": None, "turns": 3}
    assert await backend.get_context(ctx_id) == merged


@pytest.mark.asyncio
async def test_returned_context_is_a_copy(backend):
    ctx_id = (await backend.create_session()).context_id
    await backend.update_context(ctx_id, {"a": 1})
    got = await backend.get_context(ctx_id)
    got["a"] = 2
    assert await backend.get_context(ctx_id) == {"a": 1}


@pytest.mark.asyncio
async def test_clear_context(backend):
    ctx_id = (await backend.create_session()).context_id
    await backend.update_context(ctx_id, {"a": 1})
    await backend.clear_context(ctx_id)
    assert await backend.get_context(ctx_id) == {}


@pytest.mark.asyncio
async def test_store_facade_delegates(backend):
    s = SessionStore(backend)
    session = await s.create_session()
    await s.update_context(session.context_id, {"k": "v"})
    assert (await s.resolve(session.tokens[0])).context_id == session.context_id
    assert await s.get_context(session.context_id) == {"k": "v"}


# ── Expiry (in-memory, with a fake clock) ───────────────────────────────

class _Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.mark.asyncio
async def test_idle_session_expires(monkeypatch):
    clock = _Clock(1000.0)
    monkeypatch.setattr(store.time, "time", clock)
    backend = InMemorySessionBackend(ttl=60)
    session = await backend.create_session()
    await backend.update_context(session.context_id, {"a": 1})
    clock.now += 61
    assert await backend.resolve(session.tokens[0]) is None
    assert await backend.get_context(session.context_id) == {}


@pytest.mark.asyncio
async def test_active_session_slides_its_ttl(monkeypatch):
    clock = _Clock(1000.0)
    monkeypatch.setattr(store.time, "time", clock)
    backend = InMemorySessionBackend(ttl=60)
    token = (await backend.create_session()).tokens[0]
    for _ in range(3):
        clock.now += 50
        assert await backend.resolve(token) is not None
    clock.now += 61
    assert await backend.resolve(token) is None


@pytest.mark.asyncio
async def test_expired_session_cannot_rotate(monkeypatch):
    clock = _Clock(1000.0)
    monkeypatch.setattr(store.time, "time", clock)
    backend = InMemorySessionBackend(ttl=60)
    token = (await backend.create_session()).tokens[0]
    clock.now += 61
    assert await backend.rotate(token) is None


# ── Redis: what the swarm depends on ────────────────────────────────────

@needs_redis
@pytest.mark.asyncio
async def test_another_pod_resolves_the_same_session():
    pod_a = _redis_backend()
    pod_b = RedisSessionBackend(REDIS_URL, ttl=60, namespace=pod_a.namespace)
    session = await pod_a.create_session()
    await pod_a.update_context(session.context_id, {"pending_plan": {"tasks": []}})
    assert (await pod_b.resolve(session.tokens[0])).context_id == session.context_id
    assert await pod_b.get_context(session.context_id) == {"pending_plan": {"tasks": []}}


@needs_redis
@pytest.mark.asyncio
async def test_redis_keys_carry_the_ttl():
    backend = _redis_backend(ttl=60)
    session = await backend.create_session()
    await backend.update_context(session.context_id, {"a": 1})
    client = backend._get_client()
    for key in (backend._sk(session.session_id), backend._tk(session.tokens[0]), backend._ck(session.context_id)):
        assert 0 < await client.ttl(key) <= 60


@pytest.mark.asyncio
async def test_unreachable_redis_degrades_without_raising():
    backend = RedisSessionBackend("redis://127.0.0.1:1/0", ttl=60)
    session = await backend.create_session()
    assert session.context_id
    assert await backend.resolve(session.tokens[0]) is None
    assert await backend.get_context(session.context_id) == {}
    assert await backend.update_context(session.context_id, {"a": 1}) == {}


# ── Backend from the environment ────────────────────────────────────────

def test_backend_from_env(monkeypatch):
    monkeypatch.delenv("SESSION_BACKEND", raising=False)
    assert isinstance(session_backend_from_env(), InMemorySessionBackend)
    monkeypatch.setenv("SESSION_BACKEND", " Redis ")
    monkeypatch.setenv("SESSION_TTL", "120")
    monkeypatch.setenv("SESSION_REDIS_URL", "redis://r:6379/2")
    backend = session_backend_from_env()
    assert isinstance(backend, RedisSessionBackend)
    assert (backend.redis_url, backend.ttl) == ("redis://r:6379/2", 120)
