"""
Sandbox — run generated code in isolation and get back a diagnosis.

Used by the Orchestrator to verify deliverables (integration review,
.abi/specs/not-implemented/sdd-pipeline/07-deliverable-integration-review.md).
Design: .abi/specs/not-implemented/code-execution-sandbox.md.

Guarantees, enforced by the backend — never by the code being run:
    - no network, no credentials (only allowlisted env vars reach it)
    - non-root, read-only root filesystem, size-limited /workspace
    - wall-clock, CPU, memory, PID and output limits
    - one sandbox per call, always destroyed

The command is chosen by the caller's domain adapter (code), never by an
LLM. Everything that comes back — stdout, stderr, result_json — is
untrusted data: parse it, never execute it.

Usage:
    from abi_core.common.sandbox import run_in_sandbox, SANDBOX_IMAGE_PYGAME

    result = await run_in_sandbox(
        files={"game.py": source.encode()},
        command=["python", "game.py"],
        image=SANDBOX_IMAGE_PYGAME,
        env={"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
    )
    if result.exit_code != 0: ...

Backends: SANDBOX_RUNTIME=docker (default) | service (sandbox-service: identity,
OPA policy, per-run limit and audit; see sandbox_service_client) | cloudrun
(not implemented yet).
"""

import base64
import io
import os
import re
import tarfile
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SANDBOX_IMAGE_PYTHON = os.getenv("SANDBOX_IMAGE_PYTHON", "abi-sandbox-python:latest")
SANDBOX_IMAGE_PYGAME = os.getenv("SANDBOX_IMAGE_PYGAME", "abi-sandbox-pygame:latest")

# Only these variables may be passed into a sandbox. Anything else is
# rejected, so a caller can never forward its own environment (and with
# it, credentials) by accident.
ALLOWED_ENV = frozenset({
    "SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "PYTHONHASHSEED",
    "LANG", "LC_ALL", "TZ",
})
ALLOWED_ENV_PREFIX = "ABI_ACCEPTANCE_"

# Entry-point contract (sandbox-images/entry.py). A single env string is
# capped at 128 KiB by Linux (MAX_ARG_STRLEN); chunks stay well below it.
_BUNDLE_VAR = "ABI_SANDBOX_BUNDLE_{}"
_BUNDLE_CHUNK = 96 * 1024
MAX_BUNDLE_BYTES = 1024 * 1024          # encoded, all chunks together
RESULT_BEGIN = "<<<ABI_SANDBOX_RESULT_BEGIN>>>"
RESULT_END = "<<<ABI_SANDBOX_RESULT_END>>>"

_SAFE_PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*$")


@dataclass(frozen=True)
class SandboxLimits:
    timeout_s: int = 60
    cpus: float = 1.0
    memory_mb: int = 512
    pids: int = 128
    workspace_mb: int = 64
    max_output_bytes: int = 64 * 1024
    max_result_bytes: int = 256 * 1024

    def __post_init__(self):
        if not 1 <= self.timeout_s <= 300:
            raise ValueError("timeout_s must be between 1 and 300")


DEFAULT_LIMITS = SandboxLimits()


@dataclass
class SandboxResult:
    exit_code: Optional[int]
    timed_out: bool = False
    oom_killed: bool = False
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    result_json: Optional[str] = None   # raw text — untrusted, parse with care
    duration_s: float = 0.0
    error: Optional[str] = None          # the sandbox itself failed (not the code)
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and not self.timed_out and not self.oom_killed and self.exit_code == 0


def validate_env(env: Optional[Dict[str, str]]) -> Dict[str, str]:
    env = dict(env or {})
    for key in env:
        if key not in ALLOWED_ENV and not key.startswith(ALLOWED_ENV_PREFIX):
            raise ValueError(f"env var '{key}' is not allowed in a sandbox")
    return {k: str(v) for k, v in env.items()}


def build_bundle(files: Dict[str, bytes]) -> Dict[str, str]:
    """Pack files into the ABI_SANDBOX_BUNDLE_N env vars (entry.py contract)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, content in sorted(files.items()):
            if not _SAFE_PATH.match(path) or ".." in path.split("/"):
                raise ValueError(f"unsafe file path for sandbox: {path!r}")
            data = content.encode() if isinstance(content, str) else content
            info = tarfile.TarInfo(name=path)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
    encoded = base64.b64encode(buf.getvalue()).decode()
    if len(encoded) > MAX_BUNDLE_BYTES:
        raise ValueError(f"sandbox bundle too large: {len(encoded)} bytes encoded (max {MAX_BUNDLE_BYTES})")
    return {
        _BUNDLE_VAR.format(i): encoded[start:start + _BUNDLE_CHUNK]
        for i, start in enumerate(range(0, len(encoded), _BUNDLE_CHUNK))
    }


def split_result(stdout: str):
    """Separate the entry point's result block from the program's stdout."""
    begin = stdout.rfind(RESULT_BEGIN)
    if begin == -1:
        return stdout, None
    end = stdout.find(RESULT_END, begin)
    if end == -1:
        return stdout, None
    payload = stdout[begin + len(RESULT_BEGIN):end].strip()
    try:
        result = base64.b64decode(payload, validate=True).decode("utf-8", errors="replace")
    except Exception:
        result = None
    return stdout[:begin].rstrip("\n"), result


def truncate_tail(text: str, limit: int):
    """Keep the end — tracebacks are at the bottom."""
    data = text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return text, False
    return "…[truncated]…\n" + data[-limit:].decode("utf-8", errors="replace"), True


def _backend() -> str:
    return os.getenv("SANDBOX_RUNTIME", "docker").strip().lower()


async def run_in_sandbox(
    files: Dict[str, bytes],
    command: List[str],
    image: str = SANDBOX_IMAGE_PYTHON,
    env: Optional[Dict[str, str]] = None,
    limits: SandboxLimits = DEFAULT_LIMITS,
    backend: Optional[str] = None,
) -> SandboxResult:
    """Run `command` over `files` in a fresh, isolated sandbox.

    `backend` overrides SANDBOX_RUNTIME — sandbox-service passes "docker" so
    it never depends on (or loops through) its own environment."""
    # A str is iterable and its characters are str: without the type check,
    # "python t.py" passed. The sandbox-service forwards the HTTP body as is.
    if (not isinstance(command, (list, tuple)) or not command
            or not all(isinstance(c, str) for c in command)):
        raise ValueError("command must be a non-empty list of strings")
    safe_env = validate_env(env)
    bundle = build_bundle(files)

    backend = (backend or _backend()).strip().lower()
    if backend == "docker":
        from abi_core.common import sandbox_docker
        return await sandbox_docker.run(image, command, safe_env, bundle, limits)
    if backend == "service":
        # Validated above (env allowlist, paths, size); the service checks again.
        from abi_core.common import sandbox_service_client
        return await sandbox_service_client.run(files, command, image, safe_env, limits)
    raise NotImplementedError(f"SANDBOX_RUNTIME={backend!r} is not implemented")


async def sweep_sandboxes(max_age_seconds: int = 600) -> int:
    """Remove sandbox containers left behind (caller crashed mid-run)."""
    if _backend() == "docker":
        from abi_core.common import sandbox_docker
        return await sandbox_docker.sweep(max_age_seconds)
    return 0
