"""
Docker backend for abi_core.common.sandbox — local deployments.

The isolation settings below are module constants, not parameters: a
caller can choose the image, the command and the (allowlisted) env, never
the network, user or capabilities. Forgetting one of them would silently
turn the sandbox into an ordinary container.

Docker containers share the host kernel. SANDBOX_DOCKER_RUNTIME=runsc
(gVisor, if installed) adds a barrier against kernel-level escapes.
"""

import asyncio
import os
import time
import uuid
from typing import Dict, List

from abi_core.common.container_runtime import _get_docker_client
from abi_core.common.sandbox import (
    SandboxLimits,
    SandboxResult,
    split_result,
    truncate_tail,
)
from abi_core.common.utils import abi_logging

_LABEL = "abi-sandbox"
_SANDBOX_USER = "10001:10001"

# Margin over the sandbox's own timeout for Docker API calls themselves
# (create, start, logs, remove). Raised from 30s after a live run on
# 2026-10-05 exceeded timeout+30s while the same call took timeout+0.4s
# minutes later — margin for a slow daemon, not for the program.
_API_TIMEOUT = 60


def _isolation(limits: SandboxLimits) -> dict:
    opts = dict(
        network_mode="none",
        read_only=True,
        user=_SANDBOX_USER,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        tmpfs={
            "/workspace": f"size={limits.workspace_mb}m,mode=1777",
            "/tmp": "size=16m,mode=1777",
        },
        mem_limit=f"{limits.memory_mb}m",
        memswap_limit=f"{limits.memory_mb}m",
        pids_limit=limits.pids,
        nano_cpus=int(limits.cpus * 1e9),
        # Cap what a chatty program can write to the host's disk through
        # the log driver; we only ever read the tail.
        log_config={"type": "json-file", "config": {"max-size": "1m", "max-file": "1"}},
    )
    runtime = os.getenv("SANDBOX_DOCKER_RUNTIME", "")
    if runtime:
        opts["runtime"] = runtime
    return opts


def _run_sync(image: str, command: List[str], env: Dict[str, str],
              bundle: Dict[str, str], limits: SandboxLimits) -> SandboxResult:
    client = _get_docker_client()
    name = f"abi-sandbox-{uuid.uuid4().hex[:12]}"
    container = None
    started = time.monotonic()
    timed_out = False

    try:
        container = client.containers.create(
            image,
            command=command,
            name=name,
            environment={**env, **bundle,
                         "ABI_SANDBOX_MAX_RESULT_BYTES": str(limits.max_result_bytes)},
            labels={_LABEL: "true", f"{_LABEL}-created": str(int(time.time()))},
            detach=True,
            **_isolation(limits),
        )
        container.start()
        try:
            status = container.wait(timeout=limits.timeout_s)
            exit_code = status.get("StatusCode")
        except Exception:
            # requests' ReadTimeout / ConnectionError — the run exceeded
            # its wall clock. Kill, don't wait for a graceful stop.
            timed_out = True
            exit_code = None
            try:
                container.kill()
            except Exception:
                pass

        duration = time.monotonic() - started
        container.reload()
        oom = bool(container.attrs.get("State", {}).get("OOMKilled"))

        raw_out = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        raw_err = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        raw_out, result_json = split_result(raw_out)
        stdout, out_cut = truncate_tail(raw_out, limits.max_output_bytes)
        stderr, err_cut = truncate_tail(raw_err, limits.max_output_bytes)

        return SandboxResult(
            exit_code=exit_code,
            timed_out=timed_out,
            oom_killed=oom,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=out_cut,
            stderr_truncated=err_cut,
            result_json=result_json,
            duration_s=round(duration, 2),
        )

    except Exception as e:
        return SandboxResult(exit_code=None, error=f"sandbox failed: {e}",
                             duration_s=round(time.monotonic() - started, 2))
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception as e:
                abi_logging(f"[⚠️] Could not remove sandbox '{name}': {e}", level="warning")


async def run(image: str, command: List[str], env: Dict[str, str],
              bundle: Dict[str, str], limits: SandboxLimits) -> SandboxResult:
    abi_logging(f"[🧪] Sandbox: {image} {' '.join(command)}")
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_sync, image, command, env, bundle, limits),
            timeout=limits.timeout_s + _API_TIMEOUT,
        )
    except asyncio.TimeoutError:
        # The worker thread may still finish (and remove its container) in
        # the background; sweep() catches it if it doesn't.
        result = SandboxResult(exit_code=None, timed_out=True,
                               error="sandbox did not return within its time budget")
    abi_logging(
        f"[🧪] Sandbox done: exit={result.exit_code} timed_out={result.timed_out} "
        f"oom={result.oom_killed} {result.duration_s}s"
        + (f" error={result.error}" if result.error else "")
    )
    return result


def _sweep_sync(max_age_seconds: int) -> int:
    client = _get_docker_client()
    cutoff = time.time() - max_age_seconds
    removed = 0
    for c in client.containers.list(all=True, filters={"label": f"{_LABEL}=true"}):
        try:
            created = int(c.labels.get(f"{_LABEL}-created", "0"))
        except ValueError:
            created = 0
        if created < cutoff:
            try:
                c.remove(force=True)
                removed += 1
            except Exception:
                pass
    return removed


async def sweep(max_age_seconds: int) -> int:
    removed = await asyncio.to_thread(_sweep_sync, max_age_seconds)
    if removed:
        abi_logging(f"[🧹] Removed {removed} leftover sandbox container(s)")
    return removed
