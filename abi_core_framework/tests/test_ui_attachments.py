"""Files attached to a chat message reach the agent: the UI puts them in the
artifact store and sends their keys with the text.
Spec: back-office-route.md (decision 6, 2026-11-08)."""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")

from abi_core.ui import chainlit_app  # noqa: E402


class _Store:
    uploads = {}

    async def upload_file(self, key, path):
        with open(path, "rb") as f:
            _Store.uploads[key] = f.read()
        return key


def _fake_cl(monkeypatch):
    fake = SimpleNamespace(context=SimpleNamespace(session=SimpleNamespace(thread_id="t1")))
    monkeypatch.setattr(chainlit_app, "cl", fake)
    import abi_core.common.artifact_store as artifact_store
    monkeypatch.setattr(artifact_store, "ArtifactStore", _Store)
    _Store.uploads = {}


def test_attachments_go_to_the_store_and_too_big_ones_are_left_out(tmp_path, monkeypatch):
    _fake_cl(monkeypatch)
    small, big = tmp_path / "ventas.csv", tmp_path / "grande.xlsx"
    small.write_bytes(b"a,b\n1,2\n")
    big.write_bytes(b"x" * 11)
    monkeypatch.setattr(chainlit_app, "ATTACHMENT_MAX_BYTES", 10)
    elements = [SimpleNamespace(path=str(small), name="ventas.csv", mime="text/csv"),
                SimpleNamespace(path=str(big), name="grande.xlsx", mime=""),
                SimpleNamespace(path=None, name="sin archivo")]
    out = asyncio.run(chainlit_app._upload_attachments(elements))
    assert len(out) == 1 and out[0]["name"] == "ventas.csv" and out[0]["mime"] == "text/csv" and out[0]["size"] == 8
    assert out[0]["key"].startswith("attachments/t1/") and out[0]["key"].endswith("/ventas.csv")
    assert _Store.uploads[out[0]["key"]] == b"a,b\n1,2\n"


def test_the_client_sends_attachments_only_when_there_are_some(monkeypatch):
    import httpx
    from abi_core.client.agent_stream_client import AgentStreamClient
    sent = []

    class _Resp:
        headers = {}
        status_code = 200

        async def aiter_lines(self):
            if False:
                yield ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, json=None, headers=None):
            sent.append(json)
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    client = AgentStreamClient("http://agent")

    async def no_session():
        return None
    monkeypatch.setattr(client, "ensure_session", no_session)

    async def drain(**kw):
        return [x async for x in client.stream("hola", **kw)]
    asyncio.run(drain())
    asyncio.run(drain(attachments=[{"key": "attachments/t1/a/x.csv", "name": "x.csv"}]))
    assert "attachments" not in sent[0]
    assert sent[1]["attachments"] == [{"key": "attachments/t1/a/x.csv", "name": "x.csv"}]
