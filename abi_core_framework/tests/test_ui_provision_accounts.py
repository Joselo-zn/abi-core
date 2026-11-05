"""The Chat UI asks the provisioner for a user's accounts once, at chat start.
Spec: .abi/specs/not-implemented/gcp-workflows/v1/01-principales-y-cuentas.md
"""

import asyncio
from types import SimpleNamespace

import httpx
import pytest

pytest.importorskip("chainlit")

_REAL_CLIENT = httpx.AsyncClient


@pytest.fixture
def app(monkeypatch):
    from abi_core.ui import chainlit_app
    monkeypatch.setenv("ABI_UI_PROVISION_URL", "http://provisioner")
    monkeypatch.setenv("HOP_SECRET_CHATUI_PROVISIONER", "hop")
    return chainlit_app


def _run(app, monkeypatch, metadata, status=200):
    from chainlit.context import context_var
    import chainlit.data as cl_data
    sent, saved = [], []

    def handler(request):
        sent.append(request)
        return httpx.Response(status, json={"status": "ready"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))

    class DataLayer:
        async def create_user(self, user):
            saved.append(user.metadata)

    monkeypatch.setattr(cl_data, "get_data_layer", lambda: DataLayer())
    user = SimpleNamespace(id="user-1", identifier="id:abc", metadata=metadata)

    async def go():
        context_var.set(SimpleNamespace(session=SimpleNamespace(user=user)))
        await app._provision_user_accounts()

    asyncio.run(go())
    return sent, saved, user


def test_first_chat_provisions_and_marks_the_user(app, monkeypatch):
    from abi_core.security.identity_chain import get_id, verify_chain
    sent, saved, user = _run(app, monkeypatch, {"is_admin": False})
    assert len(sent) == 1 and str(sent[0].url) == "http://provisioner/provision"
    chain = __import__("json").loads(sent[0].content)["identity_chain"]
    assert verify_chain("hop", chain) and get_id(chain, "user_id") == "user-1"
    assert saved == [{"is_admin": False, "workflow_accounts": "ready"}]
    assert user.metadata["workflow_accounts"] == "ready"


def test_already_provisioned_or_failed_does_not_mark(app, monkeypatch):
    sent, saved, _ = _run(app, monkeypatch, {"workflow_accounts": "ready"})
    assert sent == [] and saved == []
    sent, saved, user = _run(app, monkeypatch, {}, status=502)
    assert len(sent) == 1 and saved == [] and "workflow_accounts" not in user.metadata


def test_off_without_the_url(app, monkeypatch):
    monkeypatch.delenv("ABI_UI_PROVISION_URL")
    sent, saved, _ = _run(app, monkeypatch, {})
    assert sent == [] and saved == []
