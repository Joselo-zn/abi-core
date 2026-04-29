"""
abi_core.tui.services — Backend connectors for the TUI.

Atomic service classes that can be used independently:
- DockerService: container listing, logs, ephemeral management
- OllamaService: model listing
- OrchestratorClient: SSE query streaming
"""

from __future__ import annotations

import json
import time
from typing import AsyncIterator

import httpx

try:
    import docker
    _DOCKER_OK = True
except ImportError:
    _DOCKER_OK = False


# ── Docker ───────────────────────────────────────────────────────

class DockerService:
    """Thin wrapper around the Docker SDK for container operations."""

    def __init__(self):
        self._client = None
        if _DOCKER_OK:
            try:
                self._client = docker.from_env()
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._client is not None

    # -- containers ------------------------------------------------

    def list_services(self, project_filter: str = "") -> list[dict]:
        """Return running/stopped containers as service dicts.

        Args:
            project_filter: If set, only return containers from this
                            Docker Compose project name.
        """
        if not self._client:
            return []
        try:
            containers = self._client.containers.list(all=True)
        except Exception:
            return []

        result = []
        for c in containers:
            labels = c.labels or {}
            project = labels.get("com.docker.compose.project", "")

            # Filter by project if specified
            if project_filter and project != project_filter:
                continue

            service = labels.get("com.docker.compose.service", c.name)
            port = self._first_port(c)
            result.append({
                "name": service,
                "type": self._guess_type(service),
                "port": port,
                "status": c.status,
                "health": self._health(c),
                "id": c.short_id,
                "project": project,
            })
        return result

    def list_ephemeral(self) -> list[dict]:
        if not self._client:
            return []
        out = []
        try:
            for c in self._client.containers.list(all=True):
                if "ephemeral" in c.name.lower():
                    state = c.attrs.get("State", {})
                    out.append({
                        "name": c.name,
                        "status": c.status,
                        "started": state.get("StartedAt", ""),
                        "finished": state.get("FinishedAt", ""),
                    })
        except Exception:
            pass
        return out

    def cleanup_ephemeral(self) -> int:
        """Remove stopped ephemeral containers. Returns count."""
        if not self._client:
            return 0
        removed = 0
        try:
            for c in self._client.containers.list(
                all=True, filters={"status": "exited"}
            ):
                if "ephemeral" in c.name.lower():
                    c.remove()
                    removed += 1
        except Exception:
            pass
        return removed

    async def stream_logs(
        self, container_name: str, tail: int = 50
    ) -> AsyncIterator[str]:
        """Yield log lines from *container_name* (exact or partial match)."""
        if not self._client:
            yield "[error] Docker not available"
            return
        container = self._find(container_name)
        if not container:
            yield f"[error] Container '{container_name}' not found"
            return
        try:
            for line in container.logs(stream=True, follow=True, tail=tail):
                yield line.decode("utf-8", errors="replace").rstrip("\n")
        except Exception as exc:
            yield f"[error] Log stream ended: {exc}"

    async def stream_compose_logs(self, tail: int = 50) -> AsyncIterator[str]:
        """Stream interleaved logs from all compose containers."""
        import asyncio
        import subprocess

        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "logs", "-f", "--tail", str(tail),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8", errors="replace").rstrip("\n")
        except asyncio.CancelledError:
            proc.terminate()
        except Exception as exc:
            yield f"[error] Compose log stream ended: {exc}"
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    # -- internals -------------------------------------------------

    def _find(self, name: str):
        try:
            return self._client.containers.get(name)
        except Exception:
            pass
        try:
            for c in self._client.containers.list(all=True):
                if name in c.name:
                    return c
        except Exception:
            pass
        return None

    @staticmethod
    def _first_port(container) -> str:
        for _, bindings in (container.ports or {}).items():
            if bindings:
                return bindings[0].get("HostPort", "")
        return ""

    @staticmethod
    def _guess_type(name: str) -> str:
        n = name.lower()
        if any(k in n for k in ("orchestrator", "planner", "builder")):
            return "agent"
        if any(k in n for k in ("guardian", "opa")):
            return "security"
        if any(k in n for k in ("semantic", "weaviate")):
            return "semantic"
        if "ollama" in n:
            return "model-server"
        if "minio" in n:
            return "storage"
        return "service"

    @staticmethod
    def _health(container) -> str:
        try:
            return container.attrs.get("State", {}).get("Health", {}).get("Status", "")
        except Exception:
            return ""


# ── Ollama ───────────────────────────────────────────────────────

class OllamaService:
    """Query the Ollama HTTP API."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.host}/api/tags")
                r.raise_for_status()
                models = []
                for m in r.json().get("models", []):
                    sz = m.get("size", 0)
                    label = f"{sz / 2**30:.1f}GB" if sz >= 2**30 else f"{sz / 2**20:.0f}MB"
                    models.append({"name": m.get("name", "?"), "size": label})
                return models
        except Exception:
            return []


# ── Orchestrator SSE client ──────────────────────────────────────

class OrchestratorClient:
    """Stream queries to an orchestrator's /stream SSE endpoint."""

    def __init__(self, url: str = "http://localhost:8000"):
        self.url = url.rstrip("/")

    async def ask(
        self, query: str, context_id: str = "cli-session"
    ) -> AsyncIterator[dict]:
        task_id = f"task-{int(time.time())}"
        payload = {"query": query, "context_id": context_id, "task_id": task_id}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0)
            ) as client:
                async with client.stream(
                    "POST", f"{self.url}/stream", json=payload
                ) as resp:
                    buf = ""
                    async for chunk in resp.aiter_text():
                        buf += chunk
                        while "\n\n" in buf:
                            raw, buf = buf.split("\n\n", 1)
                            raw = raw.strip()
                            if not raw:
                                continue
                            evt, data = "message", ""
                            for ln in raw.split("\n"):
                                if ln.startswith("event:"):
                                    evt = ln[6:].strip()
                                elif ln.startswith("data:"):
                                    data = ln[5:].strip()
                            if evt == "done":
                                yield {"event": "done"}
                                return
                            if evt == "error":
                                yield {"event": "error", "data": data}
                                return
                            if data:
                                try:
                                    yield {"event": evt, "data": json.loads(data)}
                                except json.JSONDecodeError:
                                    yield {"event": evt, "data": data}
        except httpx.ConnectError:
            yield {"event": "error", "data": "Cannot connect to orchestrator"}
        except Exception as exc:
            yield {"event": "error", "data": str(exc)}
