"""ID tokens for Cloud Run ephemerals, and ephemerals created with IAM on.
No network: the metadata server and the target are stubbed.
Spec: .abi/specs/not-implemented/ephemeral-invoker-iam.md
"""

import asyncio

import httpx
import pytest

from abi_core.common import cloudrun_auth
from abi_core.common.cloudrun_auth import CloudRunIdToken


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cloudrun_auth._cache.clear()
    calls = []

    async def fetch(audience):
        calls.append(audience)
        return f"tok-{len(calls)}"

    monkeypatch.setattr(cloudrun_auth, "_fetch_async", fetch)
    return calls


def _send(url):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200)

    async def go():
        async with httpx.AsyncClient(auth=CloudRunIdToken(), transport=httpx.MockTransport(handler)) as c:
            await c.get(url)

    asyncio.run(go())
    return seen["auth"]


def test_a_cloud_run_call_carries_an_id_token_for_its_service(monkeypatch, _clean):
    monkeypatch.setenv("K_SERVICE", "abi-swarm-orchestrator-alpha")
    assert _send("https://ephemeral-x-1.region.run.app/.well-known/agent-card.json") == "Bearer tok-1"
    assert _clean == ["https://ephemeral-x-1.region.run.app"]          # audience: the service, no path


def test_no_token_off_cloud_run_or_to_another_host(monkeypatch, _clean):
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert _send("https://ephemeral-x-1.region.run.app/health") is None
    monkeypatch.setenv("K_SERVICE", "svc")
    assert _send("http://abi-swarm-planner:11437/health") is None
    assert _clean == []


def test_the_token_is_reused_per_audience_until_it_ages(monkeypatch, _clean):
    monkeypatch.setenv("K_SERVICE", "svc")
    assert _send("https://a.run.app/x") == "Bearer tok-1"
    assert _send("https://a.run.app/y") == "Bearer tok-1"               # cached
    assert _send("https://b.run.app/") == "Bearer tok-2"                # another audience
    aud, (tok, at) = "https://a.run.app", cloudrun_auth._cache["https://a.run.app"]
    cloudrun_auth._cache[aud] = (tok, at - cloudrun_auth.TOKEN_TTL_S - 1)
    assert _send("https://a.run.app/z") == "Bearer tok-3"               # renewed


def test_ephemerals_are_created_with_iam_on(monkeypatch):
    pytest.importorskip("google.cloud.run_v2")
    from abi_core.common import cloudrun_runtime
    service = cloudrun_runtime._build_service(image="img", env_vars={}, port=8000, entrypoint=None, command=None)
    assert not service.invoker_iam_disabled
    assert service.ingress.name == "INGRESS_TRAFFIC_INTERNAL_ONLY"


def test_the_builders_health_wait_sends_the_token(monkeypatch, _clean):
    """Found live 2026-10-31: check_container_health used urllib without a token, so
    every /health got a 403 until the 600 s timeout."""
    import urllib.request
    from abi_core.common import container_runtime
    monkeypatch.setenv("K_SERVICE", "abi-swarm-builder-alpha")
    sent = []

    def urlopen(req, timeout=None):
        sent.append(req.get_header("Authorization"))

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    ok = asyncio.run(container_runtime.check_container_health("https://ephemeral-x-1.region.run.app/health", timeout=5, interval=0.01))
    assert ok and sent == ["Bearer tok-1"]
