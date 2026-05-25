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
"""

import asyncio
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging

_docker_client = None


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
    """Poll a health endpoint until ready or timeout."""
    import urllib.request

    for _ in range(int(timeout / interval)):
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=2)
            abi_logging(f"[✅] Health check passed: {url}")
            return True
        except Exception as e:
            await asyncio.sleep(interval)

    abi_logging(f"[⚠️] Health check timeout after {timeout}s: {url}")

    # Dump container logs to understand why it's not responding
    if container_name:
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

        container = await asyncio.to_thread(
            client.containers.run,
            image,
            command=command,
            name=name,
            detach=True,
            environment=environment,
            network=network,
            ports=ports,
            entrypoint=entrypoint,
        )

        container_id = container.short_id
        abi_logging(f"[✅] Container '{name}' started (id: {container_id})")

        healthy = True
        if health_check_url:
            healthy = await check_container_health(
                health_check_url, timeout=health_timeout, container_name=name
            )

        url = f"http://{name}:{port}" if port else None

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
    abi_logging(f"[🗑️] Destroying container '{name}'")

    try:
        client = _get_docker_client()
        container = await asyncio.to_thread(client.containers.get, name)
        await asyncio.to_thread(container.remove, force=True)
        abi_logging(f"[✅] Container '{name}' destroyed")
        return True
    except Exception as e:
        abi_logging(f"[⚠️] Could not destroy '{name}': {e}")
        return False
