"""Chat UI extension points.
Spec: .abi/specs/not-implemented/ui-extensions.md
"""

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")

from fastapi import Depends  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from abi_core.ui import extensions  # noqa: E402
from abi_core.ui.extensions import UIExtensions  # noqa: E402


@pytest.fixture
def fresh(monkeypatch):
    """A clean registry for the module-level helpers."""
    reg = UIExtensions()
    monkeypatch.setattr(extensions, "ui", reg)
    return reg


def run(coro):
    return asyncio.run(coro)


def test_a_route_is_served_before_chainlits_catch_all_and_hides_errors():
    from chainlit.server import app
    ui = UIExtensions(app=app)

    @ui.route("get", "/ext-test-ok")
    async def ok():
        return {"from": "extension"}

    @ui.route("post", "/ext-test-boom")
    async def boom(body: dict):
        raise ValueError(f"secret {body['value']}")

    client = TestClient(app)
    assert client.get("/ext-test-ok").json() == {"from": "extension"}
    resp = client.post("/ext-test-boom", json={"value": "s3cr3t"})
    assert resp.status_code == 500 and "s3cr3t" not in resp.text
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") not in ("/ext-test-ok", "/ext-test-boom")]


def test_require_user_refuses_without_a_session():
    from chainlit.server import app
    ui = UIExtensions(app=app)

    @ui.route("get", "/ext-test-private")
    async def private(user=Depends(ui.require_user)):
        return {"ok": True}

    assert TestClient(app).get("/ext-test-private").status_code == 401
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/ext-test-private"]


def test_a_command_or_a_claiming_hook_keeps_the_message_from_the_agent(fresh):
    seen = []

    async def create(message):
        seen.append(("command", message.content))

    async def attachments(message):
        seen.append(("hook", message.content))
        return bool(getattr(message, "elements", None))

    fresh.command("create_workflow", "Crear workflow", "workflow", create)
    fresh.on_message(attachments)
    assert run(extensions.handle_message(SimpleNamespace(command="create_workflow", content="a"))) is True
    assert run(extensions.handle_message(SimpleNamespace(command=None, content="b", elements=["file"]))) is True
    assert run(extensions.handle_message(SimpleNamespace(command=None, content="c", elements=[]))) is False
    assert seen == [("command", "a"), ("hook", "b"), ("hook", "c")]


def test_a_broken_extension_is_skipped(fresh, monkeypatch):
    good = types.ModuleType("ext_good")
    good.register = lambda ui: ui.starter("Automatizar un proceso", "Quiero automatizar…", "workflow")
    bad = types.ModuleType("ext_bad")
    bad.register = lambda ui: 1 / 0
    monkeypatch.setitem(sys.modules, "ext_good", good)
    monkeypatch.setitem(sys.modules, "ext_bad", bad)
    assert extensions.load("ext_bad, ext_missing, ext_good") == ["ext_good"]
    assert fresh.registry.starters == [("Automatizar un proceso", "Quiero automatizar…", "workflow")]


def test_identity_chain_from_a_chat_and_from_a_route(monkeypatch):
    from chainlit.context import context_var
    from abi_core.security.identity_chain import get_id, verify_chain
    monkeypatch.setenv("HOP_X", "hop")
    ui = UIExtensions()
    user = SimpleNamespace(id="user-1", metadata={"is_admin": True})

    async def in_chat():
        context_var.set(SimpleNamespace(session=SimpleNamespace(user=user, thread_id="t-1")))
        return ui.identity_chain("HOP_X")

    chain = run(in_chat())
    assert verify_chain("hop", chain)
    assert [link["id_type"] for link in chain] == ["user_id", "thread_id", "role"]
    from_route = ui.identity_chain("HOP_X", user_id="user-2", extra=[("workflow_id", "wf-1")])
    assert verify_chain("hop", from_route) and get_id(from_route, "workflow_id") == "wf-1"
    assert get_id(from_route, "user_id") == "user-2" and get_id(from_route, "role") is None
    monkeypatch.delenv("HOP_X")
    assert ui.identity_chain("HOP_X", user_id="user-2") is None


def test_csrf_tokens_are_bound_to_the_user_and_expire(monkeypatch):
    monkeypatch.setenv("CHAINLIT_AUTH_SECRET", "s")
    ui = UIExtensions()
    token = ui.csrf_token("user-1", now=1000)
    assert ui.verify_csrf("user-1", token, now=1500)
    assert not ui.verify_csrf("user-2", token, now=1500)
    assert not ui.verify_csrf("user-1", token, now=1000 + 3601)
    assert not ui.verify_csrf("user-1", "garbage", now=1500)


def test_resume_hooks_run_after_the_thread_is_on_the_page(fresh, monkeypatch):
    monkeypatch.setattr(extensions, "RESUME_DELAY_S", 0.01)
    seen = []

    @fresh.on_chat_resume
    async def welcome_back(thread):
        seen.append(thread["id"])

    async def go():
        await extensions.run_chat_resume({"id": "t-9"})
        assert seen == []                                # not before the delay
        await asyncio.sleep(0.05)

    run(go())
    assert seen == ["t-9"]


def test_a_header_link_exists_only_once_and_only_when_registered(monkeypatch):
    from chainlit.config import config
    monkeypatch.setattr(config.ui, "header_links", None)
    ui = UIExtensions()
    ui.header_link("workflows", "/workflows", "/public/workflow.svg", display_name="Workflows")
    ui.header_link("workflows", "/workflows", "/public/workflow.svg", display_name="Workflows")
    assert [(l.name, l.url, l.target) for l in config.ui.header_links] == [("workflows", "/workflows", "_self")]


def test_starters_hide_the_greeting(monkeypatch):
    from abi_core.ui import chainlit_app
    sent = []

    class Msg:
        def __init__(self, content):
            self.content = content

        async def send(self):
            sent.append(self.content)

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(chainlit_app.cl, "Message", Msg)
    monkeypatch.setattr(chainlit_app, "_sync_session_token_to_thread", noop)
    monkeypatch.setattr(chainlit_app, "_provision_user_accounts", noop)
    monkeypatch.setattr(chainlit_app._extensions, "run_chat_start", noop)
    monkeypatch.setattr(chainlit_app, "_get_client", lambda: SimpleNamespace(ensure_session=noop))
    from chainlit.context import context_var

    async def start(starters, language):
        monkeypatch.setattr(chainlit_app._extensions.ui.registry, "starters", starters)
        context_var.set(SimpleNamespace(session=SimpleNamespace(language=language)))
        await chainlit_app.on_start()

    run(start([], "es-MX"))
    run(start([("Automatizar un proceso", "…", None)], "es-MX"))
    assert len(sent) == 1 and "listo. ¿Qué quieres construir?" in sent[0]


def test_run_end_hooks_run_in_order_and_a_failing_one_does_not_stop_the_next(fresh):
    seen = []

    async def first(run):
        seen.append(("first", run["outcome"], run["error_code"]))
        raise RuntimeError("hook bug")

    async def second(run):
        seen.append(("second", run["query"]))
    fresh.on_run_end(first)
    fresh.on_run_end(second)
    run(extensions.run_run_end({"query": "crea un juego", "outcome": "failed", "error_code": "internal"}))
    assert seen == [("first", "failed", "internal"), ("second", "crea un juego")]
