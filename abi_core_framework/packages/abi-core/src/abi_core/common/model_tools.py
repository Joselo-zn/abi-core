"""
Model availability tools — framework-level, available to any ABI-Core agent.

Not tied to a single hardcoded Ollama host: `list_available_models` returns a
{model_name: host_url} registry, so the system can reason about *where* a
model lives rather than assume one endpoint. Independent of `abi_core.tui`
(alpha/experimental, not a dependency of anything else in the framework).
"""

import json
import os

import httpx

DEFAULT_TIMEOUT = 10.0
PULL_TIMEOUT = 1800.0  # long-running download, but not indefinite


def _default_hosts() -> list[str]:
    return [os.getenv("OLLAMA_HOST", "http://ollama:11434")]


async def list_available_models(hosts: list[str] | None = None) -> dict[str, str]:
    """Query one or more Ollama hosts and return {model_name: host_url}.

    A global view of which model lives where, not a boolean tied to a single
    container. Defaults to the shared host used in centralized mode.
    """
    hosts = hosts or _default_hosts()
    registry: dict[str, str] = {}
    for host in hosts:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                r = await client.get(f"{host.rstrip('/')}/api/tags")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    name = m.get("name")
                    if name:
                        registry[name] = host
        except Exception:
            continue
    return registry


async def find_model(model: str, hosts: list[str] | None = None) -> str | None:
    """Return the host URL serving `model`, or None if not found anywhere."""
    registry = await list_available_models(hosts)
    return registry.get(model)


async def pull_model(model: str, host: str | None = None):
    """Stream pull progress from `host` (defaults to the primary shared host).

    Yields the raw progress dicts from Ollama's /api/pull. Raises on
    HTTP/connection failure; callers decide how to handle it.
    """
    host = host or _default_hosts()[0]
    async with httpx.AsyncClient(timeout=PULL_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{host.rstrip('/')}/api/pull",
            json={"name": model, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
