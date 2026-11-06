"""A turn's end reaches the extensions with its outcome and error_code.
Spec: abi-core .abi/specs/not-implemented/ux/onboarding-bienvenida.md (point 7, "Lo que hace falta")
"""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")

from abi_core.ui import chainlit_app, extensions  # noqa: E402
from abi_core.ui.extensions import UIExtensions  # noqa: E402


class _Step:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.metadata = kw.get("metadata") or {}

    async def send(self):
        return self

    async def update(self):
        return self

    async def remove(self):
        return self


class _Message:
    sent = []

    def __init__(self, content="", **kw):
        self.content, self.elements = content, []

    async def send(self):
        _Message.sent.append(self.content)
        return self


def test_the_extensions_learn_how_the_turn_ended(monkeypatch):
    reg = UIExtensions()
    monkeypatch.setattr(extensions, "ui", reg)
    runs = []

    async def hook(run):
        runs.append(run)
    reg.on_run_end(hook)

    class Client:
        _token = None

        async def stream(self, query, identity_chain=None):
            yield {"response_type": "error", "content": "boom", "meta": {"error_code": "provider_unavailable"}}

    fake_cl = SimpleNamespace(
        context=SimpleNamespace(session=SimpleNamespace(language="es", thread_id="t1", id="s1"), current_step=None),
        Step=_Step, Message=_Message, user_session=SimpleNamespace(get=lambda *a, **k: None, set=lambda *a, **k: None))
    monkeypatch.setattr(chainlit_app, "cl", fake_cl)
    monkeypatch.setattr(chainlit_app, "_get_client", lambda: Client())
    monkeypatch.setattr(chainlit_app, "_build_identity_chain", lambda: None)

    async def nothing(*a, **k):
        return None
    for name in ("_expire_pending_clarification", "_sync_session_token_to_thread"):
        monkeypatch.setattr(chainlit_app, name, nothing)
    monkeypatch.setattr(chainlit_app, "_spawn_background", lambda coro: coro.close())

    asyncio.run(chainlit_app._stream_to_agent("crea un juego"))
    assert runs == [{"query": "crea un juego", "outcome": "failed", "error_code": "provider_unavailable"}]
    assert "servicio de IA" in _Message.sent[-1]
