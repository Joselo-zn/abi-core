"""ID tokens for calls between Cloud Run services.

Ephemerals on Cloud Run check IAM on every request: the caller sends a
Google ID token whose audience is the service's URL, and its account needs
roles/run.invoker. CloudRunIdToken is an httpx.Auth that adds that token to
every request to a ``*.run.app`` host, when the caller itself runs on Cloud
Run. Elsewhere (Docker, tests) it adds nothing.

The token comes from the metadata server, so no google-auth is needed (an
ephemeral may not have it). Tokens last an hour; each audience's is reused
for 50 minutes.

Spec: .abi/specs/not-implemented/ephemeral-invoker-iam.md
"""

import os
import time
from typing import Dict, Tuple

import httpx

METADATA_IDENTITY_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
TOKEN_TTL_S = 50 * 60

_cache: Dict[str, Tuple[str, float]] = {}       # audience → (token, fetched at)


def on_cloud_run() -> bool:
    """Cloud Run sets K_SERVICE in every service."""
    return bool(os.getenv("K_SERVICE"))


def audience_for(url: httpx.URL) -> str:
    """The audience Cloud Run expects: the service URL, without path."""
    return f"https://{url.host}" if url.host and url.host.endswith(".run.app") else ""


def _cached(audience: str) -> str:
    token, at = _cache.get(audience, ("", 0.0))
    return token if token and time.monotonic() - at < TOKEN_TTL_S else ""


def _store(audience: str, token: str) -> str:
    _cache[audience] = (token, time.monotonic())
    return token


def _metadata_request(audience: str) -> dict:
    return {"url": METADATA_IDENTITY_URL, "params": {"audience": audience},
            "headers": {"Metadata-Flavor": "Google"}, "timeout": 5.0}


def _fetch_sync(audience: str) -> str:
    resp = httpx.get(**_metadata_request(audience))
    resp.raise_for_status()
    return resp.text.strip()


async def _fetch_async(audience: str) -> str:
    async with httpx.AsyncClient() as metadata:
        resp = await metadata.get(**_metadata_request(audience))
    resp.raise_for_status()
    return resp.text.strip()


async def auth_header(url: str) -> Dict[str, str]:
    """{"Authorization": "Bearer …"} for a Cloud Run URL when running on Cloud
    Run, {} otherwise: for callers that do not use httpx (urllib)."""
    audience = audience_for(httpx.URL(url)) if on_cloud_run() else ""
    if not audience:
        return {}
    token = _cached(audience) or _store(audience, await _fetch_async(audience))
    return {"Authorization": f"Bearer {token}"}


class CloudRunIdToken(httpx.Auth):
    """httpx.Auth: a Google ID token on every request to a Cloud Run service."""

    def sync_auth_flow(self, request: httpx.Request):
        audience = audience_for(request.url) if on_cloud_run() else ""
        if audience:
            token = _cached(audience) or _store(audience, _fetch_sync(audience))
            request.headers["Authorization"] = f"Bearer {token}"
        yield request

    async def async_auth_flow(self, request: httpx.Request):
        audience = audience_for(request.url) if on_cloud_run() else ""
        if audience:
            token = _cached(audience) or _store(audience, await _fetch_async(audience))
            request.headers["Authorization"] = f"Bearer {token}"
        yield request
