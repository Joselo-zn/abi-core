"""
Container Runtime — Docker container lifecycle management for ABI.

Uses the Docker Python SDK (docker-py) to communicate with the Docker
daemon via the mounted socket (/var/run/docker.sock). No Docker CLI needed.

Usage:
    from abi_core.common.container_runtime import run_container, destroy_container

    result = await run_container(
        name="ephemeral_task_1",
        image="agentbase/abi-image-v2:latest",
        env_vars={"ZOMBIE_MODE": "active", "AGENT_NAME": "task_1"},
        network="abi_network",
        port=11440,
        entrypoint="python3",
        command=["/opt/abi/zombie/main.py"],
        health_check_url="http://ephemeral_task_1:11440/health",
    )

    await destroy_container("ephemeral_task_1")

Backends: CONTAINER_RUNTIME=docker (default — the Docker SDK code below) or
cloudrun (one Cloud Run service per ephemeral, see cloudrun_runtime.py).
Callers use the same functions either way; container_url() is the single
place that knows how an ephemeral is addressed in each backend.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging

# Docker SDK calls are sync, dispatched via asyncio.to_thread — the only
# real I/O in the framework with no timeout of its own (unlike e.g.
# subprocess.run(timeout=...) in library_tools.py's run_shell, which really
# kills its child process). wait_for here bounds how long a caller waits on
# that thread; it does NOT stop the thread itself — Python can't force-kill
# a running thread, so a cancelled/expired call may still complete its
# Docker operation in the background after this function has already
# returned an error. See .abi/specs/heartbeat-timeout-redesign.md.
#
# containers.run() may need to pull the image first if it isn't cached
# locally (first spawn of a given ephemeral image, or after an update) —
# generous budget for that. get()/remove() only talk to the already-running
# daemon about a container that already exists, so they stay tight.
_DOCKER_RUN_TIMEOUT = 300
_DOCKER_TEARDOWN_TIMEOUT = 30

_docker_client = None


def _backend() -> str:
    return os.getenv("CONTAINER_RUNTIME", "docker").strip().lower()


def _cloudrun():
    from abi_core.common import cloudrun_runtime
    return cloudrun_runtime


def container_url(name: str, port: Optional[int] = None) -> str:
    """Base URL other services use to reach this container.

    Docker: http://<name>:<port> on the shared network. Cloud Run: the
    service's deterministic run.app URL — known before it is deployed.
    """
    if _backend() == "cloudrun":
        return _cloudrun().container_url(name, port)
    return f"http://{name}:{port}" if port else f"http://{name}"


def _get_docker_client():
    """Lazy-init Docker client via socket."""
    global _docker_client
    if _docker_client is None:
        import docker
        _docker_client = docker.from_env()
    return _docker_client


async def check_container_health(
    url: str, timeout: int = 30, interval: float = 1.0, container_name: str = None
) -> bool:
    """Poll a health endpoint until ready, the container dies, or timeout.

    Waits as long as there is evidence of life and stops at evidence of
    death: with Docker and a container_name, a container that exited (e.g.
    its start-up `pip install` failed) ends the wait at once instead of
    burning the whole timeout. That lets the timeout be generous for slow
    but healthy start-ups — live 2026-10-05 an ephemeral's start-up pip
    install took 69s and a 60s timeout declared it unhealthy 10s before it
    was ready.
    """
    import urllib.request

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    checks = 0
    while loop.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=2)
            abi_logging(f"[✅] Health check passed: {url}")
            return True
        except Exception:
            pass
        checks += 1
        if container_name and _backend() == "docker" and checks % 5 == 0:
            try:
                container = await asyncio.to_thread(_get_docker_client().containers.get, container_name)
                if container.status in ("exited", "dead"):
                    abi_logging(f"[⚠️] Container '{container_name}' {container.status} before becoming healthy")
                    break
            except Exception:
                pass
        await asyncio.sleep(interval)
    else:
        abi_logging(f"[⚠️] Health check timeout after {timeout}s: {url}")

    # Dump container logs to understand why it's not responding (Docker only —
    # on Cloud Run they are in Cloud Logging under the service name)
    if container_name and _backend() == "docker":
        try:
            client = _get_docker_client()
            container = client.containers.get(container_name)
            state = container.attrs.get("State", {})
            abi_logging(f"[🔍] Container state: status={state.get('Status')}, running={state.get('Running')}, exit_code={state.get('ExitCode')}")
            logs = container.logs(tail=50).decode("utf-8", errors="replace")
            abi_logging(f"[📋] Container logs for '{container_name}':\n{logs}")
        except Exception as log_err:
            abi_logging(f"[⚠️] Could not fetch container logs: {log_err}")

    return False


async def run_container(
    name: str,
    image: str,
    env_vars: Optional[Dict[str, str]] = None,
    network: Optional[str] = None,
    port: Optional[int] = None,
    entrypoint: Optional[str] = None,
    command: Optional[List[str]] = None,
    health_check_url: Optional[str] = None,
    health_timeout: int = 30,
) -> Dict[str, Any]:
    """Run a Docker container via the Python SDK and optionally wait for health."""
    if _backend() == "cloudrun":
        return await _cloudrun().run_container(
            name=name, image=image, env_vars=env_vars, network=network, port=port,
            entrypoint=entrypoint, command=command,
            health_check_url=health_check_url, health_timeout=health_timeout,
        )

    abi_logging(f"[🐳] Running container '{name}' from {image}")

    try:
        client = _get_docker_client()

        # Build port bindings — skip host binding when on a Docker network
        # (containers communicate by name, no host port needed)
        ports = {}
        if port and not network:
            ports[f"{port}/tcp"] = port

        # Build environment list
        environment = [f"{k}={v}" for k, v in (env_vars or {}).items()]

        container = await asyncio.wait_for(
            asyncio.to_thread(
                client.containers.run,
                image,
                command=command,
                name=name,
                detach=True,
                environment=environment,
                network=network,
                ports=ports,
                entrypoint=entrypoint,
            ),
            timeout=_DOCKER_RUN_TIMEOUT,
        )

        container_id = container.short_id
        abi_logging(f"[✅] Container '{name}' started (id: {container_id})")

        healthy = True
        if health_check_url:
            healthy = await check_container_health(
                health_check_url, timeout=health_timeout, container_name=name
            )

        url = container_url(name, port) if port else None

        return {
            "status": "running" if healthy else "unhealthy",
            "container_id": container_id,
            "name": name,
            "url": url,
            "port": port,
            "healthy": healthy,
        }

    except Exception as e:
        abi_logging(f"[❌] Container '{name}' failed to start: {e}")
        return {
            "status": "error",
            "name": name,
            "error": str(e),
        }


async def destroy_container(name: str) -> bool:
    """Stop and remove a container by name."""
    if _backend() == "cloudrun":
        return await _cloudrun().destroy_container(name)

    abi_logging(f"[🗑️] Destroying container '{name}'")

    try:
        client = _get_docker_client()
        container = await asyncio.wait_for(
            asyncio.to_thread(client.containers.get, name), timeout=_DOCKER_TEARDOWN_TIMEOUT,
        )
        await asyncio.wait_for(
            asyncio.to_thread(container.remove, force=True), timeout=_DOCKER_TEARDOWN_TIMEOUT,
        )
        abi_logging(f"[✅] Container '{name}' destroyed")
        return True
    except Exception as e:
        abi_logging(f"[⚠️] Could not destroy '{name}': {e}")
        return False
