"""SecureDataLayer: whose key encrypts a write, and the pool's pre-ping.
No database: the owner lookups are stubbed.
Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")
pytest.importorskip("cryptography")
pytest.importorskip("asyncpg")

from chainlit.context import context_var  # noqa: E402

from abi_core.ui.crypto import SYSTEM_KEY_ID  # noqa: E402
from abi_core.ui.secure_data_layer import SecureDataLayer  # noqa: E402

URL = "postgresql+asyncpg://u:p@localhost:1/db"   # never connected to


def _layer(thread_owner=None):
    layer = SecureDataLayer(conninfo=URL)

    async def raw(query, parameters):
        return [{"u": thread_owner}] if thread_owner and "FROM threads" in query else []

    layer._raw = raw
    return layer


def _in_session(user, coro):
    async def run():
        context_var.set(SimpleNamespace(session=SimpleNamespace(user=user)))
        return await coro
    return asyncio.run(run())


def test_first_message_of_a_new_thread_takes_the_session_users_key():
    key = _in_session(SimpleNamespace(id="user-1"), _layer()._key_for("steps", {"threadId": "t-new"}))
    assert key == "user-1"


def test_the_threads_owner_wins_over_the_session():
    key = _in_session(SimpleNamespace(id="user-2"), _layer("user-1")._key_for("steps", {"threadId": "t-1"}))
    assert key == "user-1"


def test_outside_a_session_or_without_a_persisted_user_it_is_the_system_key():
    assert asyncio.run(_layer()._key_for("steps", {"threadId": "t-new"})) == SYSTEM_KEY_ID
    assert _in_session(SimpleNamespace(identifier="x"), _layer()._key_for("threads", {"id": "t-new"})) == SYSTEM_KEY_ID


def test_engines_check_connections_before_use(monkeypatch):
    layer = SecureDataLayer(conninfo=URL)
    assert layer.engine.pool._pre_ping is True
    assert layer.async_session.kw["bind"] is layer.engine
    # auth registers Chainlit's OAuth callback at import, which needs a provider.
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "test")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "test")
    from abi_core.ui import auth
    monkeypatch.setattr(auth, "DATABASE_URL", URL)
    monkeypatch.setattr(auth, "_engine", None)
    assert auth._get_engine().pool._pre_ping is True
