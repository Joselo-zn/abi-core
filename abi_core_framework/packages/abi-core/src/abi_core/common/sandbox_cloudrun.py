"""
Cloud Run Jobs backend for abi_core.common.sandbox — GCP deployments.

One Job per sandbox image, created by the deploy (not here): this module only
runs it, with the bundle, the allowlisted env and the command as per-execution
overrides — the same entry.py contract as the Docker backend. Cloud Run Jobs
accept env and args overrides per execution, not volumes, and cap each env
value at 32 768 bytes (measured 2026-10-29); the bundle is cut to fit.

Isolation that the Job (deploy) provides, not this module:
    - a microVM per execution (Jobs always run on the second generation);
    - no network: Direct VPC egress to a subnet whose firewall denies all
      egress for the Job's network tag;
    - no useful identity: a service account with no roles. Cloud Run's
      metadata server cannot be blocked (it is local to the instance, not
      egress): the code CAN fetch that account's token (measured
      2026-10-29). With no roles and no network it can only leave inside
      the output the runtime collects.
    - 1 CPU / 512 MiB, fixed per Job — `limits.cpus` and `limits.memory_mb`
      do not apply per execution here; the wall clock does (task timeout).

stdout/stderr come from Cloud Logging, so a result is up to ~10-30 s slower
than locally; the exit code comes from the task's last attempt.

Requires the optional dependency: pip install "abi-core-ai[gcp]".

Environment:
    CLOUDRUN_PROJECT       GCP project id (required)
    CLOUDRUN_REGION        e.g. northamerica-south1 (required)
    SANDBOX_CLOUDRUN_JOBS  image -> Job, e.g.
                           "abi-sandbox-python=abi-sandbox-python-alpha,
                            abi-sandbox-pygame=abi-sandbox-pygame-alpha"
                           (image name without registry or tag). An image
                           with no Job is an error, never a fallback.

Spec: .abi/specs/not-implemented/code-execution-sandbox.md
"""

import asyncio
import os
import time
from typing import Dict, List, Optional, Tuple

from abi_core.common.sandbox import (
    SandboxLimits,
    SandboxResult,
    split_result,
    truncate_tail,
)
from abi_core.common.utils import abi_logging

# A Cloud Logging entry holds up to 256 KB and entry.py prints .result.json as
# one base64 line: 128 KiB of JSON is ~175 KB encoded.
MAX_RESULT_BYTES = 128 * 1024

# Margin over the sandbox's own timeout for the API itself (queueing the
# execution, starting the microVM — 10-16 s measured — and finishing).
_API_TIMEOUT = 120
# stdout reaches Cloud Logging 1-13 s after the execution ends (measured).
_LOG_WAIT = 45
_LOG_PAGE = 1000

_LOGGING_URL = "https://logging.googleapis.com/v2/entries:list"
_STREAMS = ("stdout", "stderr", "varlog/system")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for SANDBOX backend 'cloudrun'")
    return value


def image_key(image: str) -> str:
    """'northamerica-south1-docker.pkg.dev/p/r/abi-sandbox-python:abc' -> 'abi-sandbox-python'."""
    name = image.rsplit("/", 1)[-1]
    return name.split("@", 1)[0].split(":", 1)[0]


def job_for(image: str, mapping: Optional[str] = None) -> str:
    raw = os.getenv("SANDBOX_CLOUDRUN_JOBS", "") if mapping is None else mapping
    jobs = {}
    for pair in raw.split(","):
        if "=" in pair:
            key, job = pair.split("=", 1)
            jobs[key.strip()] = job.strip()
    key = image_key(image)
    if key not in jobs or not jobs[key]:
        raise ValueError(f"no Cloud Run Job for sandbox image {key!r} (SANDBOX_CLOUDRUN_JOBS)")
    return jobs[key]


def build_request(job_path: str, command: List[str], env: Dict[str, str],
                  bundle: Dict[str, str], limits: SandboxLimits):
    from google.cloud import run_v2
    from google.protobuf import duration_pb2

    variables = {**env, **bundle,
                 "ABI_SANDBOX_MAX_RESULT_BYTES": str(min(limits.max_result_bytes, MAX_RESULT_BYTES))}
    return run_v2.RunJobRequest(
        name=job_path,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=list(command),
                env=[run_v2.EnvVar(name=k, value=v) for k, v in variables.items()],
            )],
            task_count=1,
            timeout=duration_pb2.Duration(seconds=limits.timeout_s),
        ),
    )


def attempt_outcome(task) -> Tuple[Optional[int], bool]:
    """(exit code, timed out) from a Task's last attempt."""
    result = getattr(task, "last_attempt_result", None)
    if result is None:
        return None, False
    message = (getattr(getattr(result, "status", None), "message", "") or "").lower()
    timed_out = "timeout" in message or "timed out" in message or "deadline" in message
    code = getattr(result, "exit_code", None)
    return (None if timed_out else code), timed_out


def assemble_logs(entries: List[dict]) -> Tuple[str, str, str]:
    """Cloud Logging entries (any order) -> (stdout, stderr, system)."""
    streams = {s: [] for s in _STREAMS}
    for e in entries:
        log = e.get("logName", "").rsplit("/", 1)[-1].replace("%2F", "/")
        stream = log.split("run.googleapis.com/", 1)[-1]
        if stream in streams:
            streams[stream].append((e.get("timestamp", ""), e.get("insertId", ""), e.get("textPayload", "")))
    out = {s: "\n".join(t for _, _, t in sorted(v)) for s, v in streams.items()}
    return out["stdout"], out["stderr"], out["varlog/system"]


# Cloud Run reports nothing about memory when the program runs out of it
# (measured 2026-10-29): the microVM's kernel SIGKILLs it and entry.py exits
# 247 (-9 as a byte); if entry.py itself is killed, the container exits 137.
# Nothing else sends SIGKILL inside the sandbox, so it is read as OOM.
_SIGKILL_EXITS = (137, 247)


def oom_from(system: str, exit_code: Optional[int]) -> bool:
    text = system.lower()
    if "memory limit" in text and ("exceeded" in text or "killed" in text):
        return True
    return exit_code in _SIGKILL_EXITS


def _read_logs(project: str, execution: str, finished: bool) -> List[dict]:
    import google.auth
    import google.auth.transport.requests
    import httpx

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(google.auth.transport.requests.Request())
    names = " OR ".join(f'logName="projects/{project}/logs/run.googleapis.com%2F{s.replace("/", "%2F")}"'
                        for s in _STREAMS)
    body = {
        "resourceNames": [f"projects/{project}"],
        "filter": (f'resource.type="cloud_run_job" AND '
                   f'labels."run.googleapis.com/execution_name"="{execution}" AND ({names})'),
        "orderBy": "timestamp desc",
        "pageSize": _LOG_PAGE,
    }
    entries: List[dict] = []
    deadline = time.monotonic() + _LOG_WAIT
    while True:
        resp = httpx.post(_LOGGING_URL, json=body, timeout=30,
                          headers={"Authorization": f"Bearer {credentials.token}"})
        resp.raise_for_status()
        entries = resp.json().get("entries", [])
        # The system log closes every execution ("Container called exit(N)."),
        # and lands after the program's own output.
        _, _, system = assemble_logs(entries)
        if "Container called exit" in system or not finished or time.monotonic() > deadline:
            return entries
        time.sleep(3)


def _run_sync(image: str, command: List[str], env: Dict[str, str],
              bundle: Dict[str, str], limits: SandboxLimits) -> SandboxResult:
    from google.cloud import run_v2

    started = time.monotonic()
    try:
        project, region = _require("CLOUDRUN_PROJECT"), _require("CLOUDRUN_REGION")
        job_path = f"projects/{project}/locations/{region}/jobs/{job_for(image)}"
        request = build_request(job_path, command, env, bundle, limits)

        operation = run_v2.JobsClient().run_job(request=request)
        timed_out = False
        try:
            execution = operation.result(timeout=limits.timeout_s + _API_TIMEOUT)
        except Exception:
            # A failed execution (non-zero exit, task timeout) also ends the
            # operation with an error; the execution itself is in metadata.
            execution = None
        name = getattr(execution, "name", "") or getattr(operation.metadata, "name", "")
        if not name:
            return SandboxResult(exit_code=None, error="sandbox failed: no execution was created",
                                 duration_s=round(time.monotonic() - started, 2))

        exit_code = None
        for task in run_v2.TasksClient().list_tasks(parent=name):
            exit_code, timed_out = attempt_outcome(task)
        duration = time.monotonic() - started

        stdout, stderr, system = assemble_logs(_read_logs(project, name.rsplit("/", 1)[-1], finished=True))
        stdout, result_json = split_result(stdout)
        stdout, out_cut = truncate_tail(stdout, limits.max_output_bytes)
        stderr, err_cut = truncate_tail(stderr, limits.max_output_bytes)
        oom = oom_from(system, exit_code)
        return SandboxResult(
            exit_code=None if (timed_out or oom) and exit_code in (None, 0) else exit_code,
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


async def run(image: str, command: List[str], env: Dict[str, str],
              bundle: Dict[str, str], limits: SandboxLimits) -> SandboxResult:
    abi_logging(f"[🧪] Sandbox (Cloud Run Jobs): {image_key(image)} {' '.join(command)}")
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_sync, image, command, env, bundle, limits),
            timeout=limits.timeout_s + _API_TIMEOUT + _LOG_WAIT + 30,
        )
    except asyncio.TimeoutError:
        # The execution ends on its own task timeout; nothing to clean up.
        result = SandboxResult(exit_code=None, timed_out=True,
                               error="sandbox did not return within its time budget")
    abi_logging(
        f"[🧪] Sandbox done: exit={result.exit_code} timed_out={result.timed_out} "
        f"oom={result.oom_killed} {result.duration_s}s"
        + (f" error={result.error}" if result.error else "")
    )
    return result
