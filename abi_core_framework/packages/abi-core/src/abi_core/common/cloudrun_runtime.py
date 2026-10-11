"""
Cloud Run backend for container_runtime — one Cloud Run service per ephemeral.

Selected with CONTAINER_RUNTIME=cloudrun. Callers never import this module
directly: container_runtime.py dispatches here so the Builder and the
Orchestrator keep the same calls they use with Docker.

Docker → Cloud Run mapping:
    run_container      → create_service (internal ingress, scale 0..1,
                         CPU always allocated so heartbeats keep flowing
                         outside of a request)
    destroy_container  → delete_service
    container_url      → https://<service>-<project number>.<region>.run.app
                         (deterministic, known before the service exists —
                         the Builder bakes it into the agent card it hands
                         the ephemeral at spawn)

Requires the optional dependency: pip install "abi-core-ai[gcp]".

Environment:
    CLOUDRUN_PROJECT          GCP project id (required)
    CLOUDRUN_PROJECT_NUMBER   GCP project number, for the service URL (required)
    CLOUDRUN_REGION           e.g. us-central1 (required)
    CLOUDRUN_SERVICE_ACCOUNT  identity the ephemerals run as — no Cloud Run
                              permissions of its own
    CLOUDRUN_NETWORK / CLOUDRUN_SUBNET
                              Direct VPC egress, so calls from the ephemeral
                              to other internal services count as internal
    ABI_ENV                   environment label (alpha, prod) — the sweep
                              only touches ephemerals of its own environment
    EPHEMERAL_CPU / EPHEMERAL_MEMORY / EPHEMERAL_REQUEST_TIMEOUT

See .abi/specs/not-implemented/gcp-build-deploy-pipeline.md.
"""

import asyncio
import os
import re
import time
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging

# Creating a service waits for its first revision to be ready — that
# includes pulling the image into Cloud Run. Delete is a control-plane call.
_CLOUDRUN_DEPLOY_TIMEOUT = 300
_CLOUDRUN_TEARDOWN_TIMEOUT = 60

# Cloud Run service ids: lowercase letters, digits and hyphens, start with
# a letter, no trailing hyphen, max 49 characters.
_SERVICE_ID_MAX = 49

_LABEL_EPHEMERAL = "abi-ephemeral"
_LABEL_ENV = "abi-env"
_LABEL_CREATED = "abi-created"

_client = None


def _get_client():
    """Lazy-init the async Cloud Run client (Application Default Credentials)."""
    global _client
    if _client is None:
        from google.cloud import run_v2
        _client = run_v2.ServicesAsyncClient()
    return _client


def _require(var: str) -> str:
    value = os.getenv(var, "")
    if not value:
        raise RuntimeError(f"{var} is required when CONTAINER_RUNTIME=cloudrun")
    return value


def _parent() -> str:
    return f"projects/{_require('CLOUDRUN_PROJECT')}/locations/{_require('CLOUDRUN_REGION')}"


def service_id(name: str) -> str:
    """Normalize an agent name into a valid Cloud Run service id.

    Deterministic, so spawn, URL and teardown all land on the same service.
    Builder names look like ephemeral-task-1-1759500000; when too long the
    tail (timestamp) is kept, since that's what makes the name unique.
    """
    sid = re.sub(r"[^a-z0-9-]", "-", name.lower())
    sid = re.sub(r"-+", "-", sid).strip("-")
    if len(sid) > _SERVICE_ID_MAX:
        sid = sid[-_SERVICE_ID_MAX:].lstrip("-")
    if not sid or not sid[0].isalpha():
        sid = ("e-" + sid)[:_SERVICE_ID_MAX]
    return sid.rstrip("-")


def container_url(name: str, port: Optional[int] = None) -> str:
    """Public base URL of the service. The port is internal to Cloud Run —
    every service is reached over HTTPS on 443."""
    return (
        f"https://{service_id(name)}-{_require('CLOUDRUN_PROJECT_NUMBER')}"
        f".{_require('CLOUDRUN_REGION')}.run.app"
    )


def _build_service(
    image: str,
    env_vars: Dict[str, str],
    port: Optional[int],
    entrypoint: Optional[str],
    command: Optional[List[str]],
):
    from google.cloud import run_v2
    from google.protobuf import duration_pb2

    container = run_v2.Container(
        image=image,
        env=[run_v2.EnvVar(name=k, value=str(v)) for k, v in env_vars.items()],
        resources=run_v2.ResourceRequirements(
            limits={
                "cpu": os.getenv("EPHEMERAL_CPU", "2"),
                "memory": os.getenv("EPHEMERAL_MEMORY", "4Gi"),
            },
            # CPU stays allocated outside of a request: the ephemeral keeps
            # running its post-response cleanup (artifact upload, deregister)
            # after the A2A response has been sent.
            cpu_idle=False,
            startup_cpu_boost=True,
        ),
    )
    if port:
        container.ports = [run_v2.ContainerPort(container_port=port)]
    if entrypoint:
        container.command = [entrypoint]
    if command:
        container.args = command

    template = run_v2.RevisionTemplate(
        containers=[container],
        scaling=run_v2.RevisionScaling(min_instance_count=0, max_instance_count=1),
        timeout=duration_pb2.Duration(
            seconds=int(os.getenv("EPHEMERAL_REQUEST_TIMEOUT", "3600"))
        ),
        # One task per ephemeral — never interleave two A2A requests.
        max_instance_request_concurrency=1,
    )
    sa = os.getenv("CLOUDRUN_SERVICE_ACCOUNT", "")
    if sa:
        template.service_account = sa
    network = os.getenv("CLOUDRUN_NETWORK", "")
    if network:
        template.vpc_access = run_v2.VpcAccess(
            network_interfaces=[run_v2.VpcAccess.NetworkInterface(
                network=network,
                subnetwork=os.getenv("CLOUDRUN_SUBNET", ""),
            )],
            egress=run_v2.VpcAccess.VpcEgress.ALL_TRAFFIC,
        )

    return run_v2.Service(
        template=template,
        # Reachable only from inside the project's network; the network is
        # the protection, so per-request IAM is off (no ID tokens needed by
        # the Orchestrator). Accepted for alpha — see the spec.
        ingress=run_v2.IngressTraffic.INGRESS_TRAFFIC_INTERNAL_ONLY,
        invoker_iam_disabled=True,
        labels={
            _LABEL_EPHEMERAL: "true",
            _LABEL_ENV: os.getenv("ABI_ENV", "default"),
            _LABEL_CREATED: str(int(time.time())),
        },
    )


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
    """Deploy an ephemeral as a Cloud Run service and optionally wait for health.

    `network` is a Docker concept and is ignored here (VPC comes from
    CLOUDRUN_NETWORK). Same return shape as the Docker backend.
    """
    from abi_core.common.container_runtime import check_container_health

    sid = service_id(name)
    abi_logging(f"[☁️] Deploying Cloud Run service '{sid}' from {image}")

    try:
        client = _get_client()
        service = _build_service(image, env_vars or {}, port, entrypoint, command)
        operation = await asyncio.wait_for(
            client.create_service(parent=_parent(), service=service, service_id=sid),
            timeout=_CLOUDRUN_DEPLOY_TIMEOUT,
        )
        created = await asyncio.wait_for(operation.result(), timeout=_CLOUDRUN_DEPLOY_TIMEOUT)
        url = created.uri or container_url(name, port)
        abi_logging(f"[✅] Cloud Run service '{sid}' ready at {url}")

        healthy = True
        if health_check_url:
            healthy = await check_container_health(health_check_url, timeout=health_timeout)

        return {
            "status": "running" if healthy else "unhealthy",
            "container_id": created.uid,
            "name": sid,
            "url": url,
            "port": port,
            "healthy": healthy,
        }

    except Exception as e:
        abi_logging(f"[❌] Cloud Run service '{sid}' failed to deploy: {e}")
        return {
            "status": "error",
            "name": sid,
            "error": str(e),
        }


async def destroy_container(name: str) -> bool:
    """Delete the Cloud Run service backing an ephemeral."""
    sid = service_id(name)
    abi_logging(f"[🗑️] Deleting Cloud Run service '{sid}'")

    try:
        client = _get_client()
        operation = await asyncio.wait_for(
            client.delete_service(name=f"{_parent()}/services/{sid}"),
            timeout=_CLOUDRUN_TEARDOWN_TIMEOUT,
        )
        await asyncio.wait_for(operation.result(), timeout=_CLOUDRUN_TEARDOWN_TIMEOUT)
        abi_logging(f"[✅] Cloud Run service '{sid}' deleted")
        return True
    except Exception as e:
        abi_logging(f"[⚠️] Could not delete Cloud Run service '{sid}': {e}")
        return False


async def sweep_ephemerals(max_age_seconds: int) -> List[str]:
    """Delete ephemeral services of this environment older than max_age_seconds.

    Safety net for ephemerals nobody tore down (Orchestrator restarted
    mid-plan, teardown call failed). Only touches services labelled
    abi-ephemeral=true with this ABI_ENV.
    """
    env = os.getenv("ABI_ENV", "default")
    cutoff = time.time() - max_age_seconds
    deleted: List[str] = []

    try:
        client = _get_client()
        pager = await client.list_services(parent=_parent())
        stale = []
        async for svc in pager:
            labels = dict(svc.labels)
            if labels.get(_LABEL_EPHEMERAL) != "true" or labels.get(_LABEL_ENV) != env:
                continue
            try:
                created = int(labels.get(_LABEL_CREATED, "0"))
            except ValueError:
                continue
            if created and created < cutoff:
                stale.append(svc.name.rsplit("/", 1)[-1])
    except Exception as e:
        abi_logging(f"[⚠️] Ephemeral sweep could not list services: {e}")
        return deleted

    for sid in stale:
        if await destroy_container(sid):
            deleted.append(sid)
    if deleted:
        abi_logging(f"[🧹] Swept {len(deleted)} stale ephemeral service(s): {deleted}")
    return deleted
