"""
Tests for the governed sandbox (ephemeral-reviewer-pipeline 02.5):
caller verification, the request signature, the decorator and the service's
decision path. OPA and the semantic layer are stubbed here; the policy itself
is evaluated against the real OPA binary separately.
Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.5-governed-sandbox.md
"""

import asyncio
import base64
import json
import time

import pytest

from abi_core.common import project_store, sandbox_service_client as client
from abi_core.common.sandbox import DEFAULT_LIMITS, SandboxResult
from abi_core.security.agent_auth import build_semantic_context_from_card
from abi_core.semantic.semantic_access_validator import SemanticAccessValidator

CARD = {"id": "agent://orchestrator", "name": "orchestrator",
        "auth": {"method": "hmac_sha256", "key_id": "k", "shared_secret": "s3cret"},
        "security": {"allowed_actions": ["run_sandbox"]}}


@pytest.fixture
def card_path(tmp_path):
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    path = cards / "orchestrator.json"
    path.write_text(json.dumps(CARD))
    return path


# ── verify_caller (semantic layer side) ────────────────────────

def test_verify_caller_strict(card_path):
    v = SemanticAccessValidator("", "", card_path.parent)
    ctx = build_semantic_context_from_card(str(card_path), "run_sandbox", "digest")

    ok = asyncio.run(v.verify_caller(ctx))
    assert ok["verified"] is True
    assert "auth" not in ok["card"] and ok["card"]["security"] == CARD["security"]

    assert asyncio.run(v.verify_caller({"headers": ctx["headers"]}))["reason"] == "missing signed payload"
    tampered = {"headers": ctx["headers"], "payload": {**ctx["payload"], "query": "other"}}
    assert asyncio.run(v.verify_caller(tampered))["verified"] is False
    stale = build_semantic_context_from_card(str(card_path), "run_sandbox", "d")
    stale["payload"]["ts"] = int(time.time()) - 3600
    assert "stale" in asyncio.run(v.verify_caller(stale))["reason"]
    unknown = {**ctx, "payload": {**ctx["payload"], "agent_id": "agent://nobody"}}
    unknown["headers"] = {**ctx["headers"], "X-ABI-Agent-ID": "agent://nobody"}
    assert asyncio.run(v.verify_caller(unknown))["verified"] is False


# ── decorator and client ────────────────────────────────────────

def test_sandboxed_requires_run_id(monkeypatch, card_path):
    from abi_core.agent.abi_core_app import AbiCore

    monkeypatch.setenv("AGENT_CARD", str(card_path))

    app = AbiCore(config=object(), agent_card=None)
    with pytest.raises(TypeError):
        app.sandboxed(lambda files: None)

    @app.sandboxed
    async def review(run_id):
        return client.current_caller()

    with pytest.raises(ValueError):
        asyncio.run(review(run_id=""))
    seen = asyncio.run(review(run_id="r1"))
    assert seen == {"run_id": "r1", "agent_card_path": str(card_path)}
    assert client.current_caller() is None  # reset after the call


def test_client_without_run_id_is_denied_not_raised():
    result = asyncio.run(client.run({"a.py": b"x"}, ["python", "a.py"], "img", {}, DEFAULT_LIMITS))
    assert result.error.startswith("sandbox denied") and not result.ok


# ── service decision path ───────────────────────────────────────

class FakeStore:
    def __init__(self):
        self.objects = {}

    async def ensure_bucket(self): pass
    async def ensure_expiration(self, *a): pass

    async def upload(self, key, content, metadata=None):
        self.objects[key] = content

    async def download(self, key):
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key]

    async def list_artifacts(self, prefix=""):
        return [k for k in self.objects if k.startswith(prefix)]


@pytest.fixture
def service(monkeypatch, card_path):
    """The service with a fake store, a stubbed semantic layer (the real
    validator over the test card) and a stubbed OPA that applies the policy's
    rules in Python. Returns (app module, store, sandbox calls, opa inputs)."""
    from abi_services.sandbox_service import app

    store = FakeStore()
    monkeypatch.setattr(project_store, "ArtifactStore", lambda: store)
    monkeypatch.setattr(project_store, "_retention_applied", True)
    v = SemanticAccessValidator("", "", card_path.parent)

    async def fake_verify(caller_context, _card):
        return await v.verify_caller(caller_context)

    opa_inputs = []

    async def fake_opa(opa_input, _url, _path):
        opa_inputs.append(opa_input)
        c, r = opa_input["caller"], opa_input["run"]
        ok = (c["verified"] and "run_sandbox" in c["allowed_actions"] and r["plan_exists"]
              and r["has_executable_code"] and r["runs_used"] < opa_input["limits"]["max_runs"])
        return (True, "") if ok else (False, "denied by policy")

    calls = []

    async def fake_sandbox(files, command, image, env, limits, backend=None):
        assert backend == "docker"
        calls.append((sorted(files), command))
        return SandboxResult(exit_code=0, stdout="ran")

    monkeypatch.setattr(app, "verify_caller", fake_verify)
    monkeypatch.setattr(app, "ask_opa", fake_opa)
    monkeypatch.setattr(app, "run_in_sandbox", fake_sandbox)
    monkeypatch.setenv("SANDBOX_MAX_RUNS_PER_RUN_ID", "2")
    monkeypatch.delenv("SANDBOX_RUNTIME", raising=False)
    return app, store, calls, opa_inputs


def _body(card_path, run_id="r1", files=None, command=("python", "game.py")):
    files = files or {"game.py": b"print('hi')\n"}
    from dataclasses import asdict
    limits = asdict(DEFAULT_LIMITS)
    digest = client.request_digest(run_id, files, list(command), "img", {}, limits)
    ctx = build_semantic_context_from_card(str(card_path), client.SANDBOX_ACTION, digest)
    return {"run_id": run_id, "caller_context": {"headers": ctx["headers"], "payload": ctx["payload"]},
            "files": {n: base64.b64encode(b).decode() for n, b in files.items()},
            "command": list(command), "image": "img", "env": {}, "limits": limits}


def _plan(store, run_id="r1", entry="game.py"):
    plan = {"technical_design": {"files": [{"filename": entry, "role": "entry_point"}]}}
    store.objects[project_store.project_key(run_id, "plan", "plan.json")] = json.dumps(plan).encode()


def _audit(store, run_id="r1"):
    raw = store.objects.get(project_store.project_key(run_id, "review", "sandbox-audit.jsonl"), b"")
    return [json.loads(l) for l in raw.decode().splitlines()]


def test_service_allows_runs_audits_and_enforces_limit(service, card_path):
    app, store, calls, opa_inputs = service
    _plan(store)

    first = asyncio.run(app.handle_run(_body(card_path)))
    second = asyncio.run(app.handle_run(_body(card_path)))
    third = asyncio.run(app.handle_run(_body(card_path)))

    assert first["allowed"] and second["allowed"] and first["result"]["stdout"] == "ran"
    assert third == {"allowed": False, "reason": "denied by policy"}   # limit 2
    assert len(calls) == 2
    assert [e["decision"] for e in _audit(store)] == ["allowed", "allowed", "denied"]
    assert opa_inputs[0]["caller"]["id"] == "agent://orchestrator"
    assert opa_inputs[2]["run"]["runs_used"] == 2


def test_service_denies_before_running(service, card_path):
    app, store, calls, _ = service
    _plan(store)

    tampered = _body(card_path)
    tampered["files"]["game.py"] = base64.b64encode(b"import os; os.system('x')").decode()
    unsigned = _body(card_path)
    del unsigned["caller_context"]["payload"]
    no_plan = _body(card_path, run_id="r2")

    assert asyncio.run(app.handle_run(tampered))["reason"] == "signature does not cover this request"
    assert asyncio.run(app.handle_run(unsigned))["reason"] == "missing signed payload"
    assert asyncio.run(app.handle_run(no_plan))["allowed"] is False
    assert calls == []
    assert [e["decision"] for e in _audit(store)] == ["denied", "denied"]
    assert _audit(store, "r2")[0]["decision"] == "denied"


def test_opa_unreachable_denies():
    from abi_services.sandbox_service.app import ask_opa

    assert asyncio.run(ask_opa({}, "", "abi/sandbox")) == (False, "OPA_URL not configured")
    allowed, reason = asyncio.run(ask_opa({}, "http://127.0.0.1:9", "abi/sandbox"))
    assert allowed is False and reason.startswith("OPA unreachable")


def test_missing_card_denies_at_run_time_only(monkeypatch):
    monkeypatch.delenv("AGENT_CARD", raising=False)
    with client.sandbox_caller("r1"):   # entering never raises
        result = asyncio.run(client.run({"a.py": b"x"}, ["python", "a.py"], "img", {}, DEFAULT_LIMITS))
    assert result.error == "sandbox denied: no agent card to sign with (AGENT_CARD)"


def test_service_card_gets_id_from_service_id(tmp_path):
    """semantic_access.rego reads `id`; a ServiceCard only has `service_id`.
    Live 2026-10-09 the sandbox-service was "not registered" and denied."""
    from abi_core.common.service_card import ServiceCard

    (tmp_path / "agent_cards").mkdir()
    (tmp_path / "service_cards").mkdir()
    card = {"service_id": "service://abi-swarm-sandbox", "name": "abi-swarm-sandbox",
            "auth": {"method": "hmac_sha256", "key_id": "k", "shared_secret": "s"}}
    (tmp_path / "service_cards" / "sandbox.json").write_text(json.dumps(card))
    v = SemanticAccessValidator("", "", tmp_path / "agent_cards")
    loaded = asyncio.run(v._load_agent_card("service://abi-swarm-sandbox"))
    assert loaded["id"] == "service://abi-swarm-sandbox"
    ctx = ServiceCard.from_dict(card).build_context(tool_name="verify_caller", query="{}")
    assert v._verify_signature(loaded, ctx)
