"""
Sandbox service client — ``SANDBOX_RUNTIME=service`` backend of
``abi_core.common.sandbox``.

The caller never runs Docker: it asks ``sandbox-service``, which verifies who
is calling (the caller's agent card, HMAC-signed, checked by the semantic
layer), asks OPA whether that run may use the sandbox, runs it and audits
the request in ``projects/<run_id>/review/sandbox-audit.jsonl``.

Every request belongs to a plan run: ``run_id`` and the signing card come
from ``sandbox_caller(...)`` — set by ``@agent.sandboxed`` — never from the
code being run or from a model. The signature covers a digest of the whole
request (run, command, image, env, limits, every file's hash), so a signed
request cannot be replayed with other files.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.5-governed-sandbox.md
"""

import base64
import contextvars
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import asdict
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from abi_core.common.sandbox import SandboxResult

SANDBOX_ACTION = "run_sandbox"

_caller: contextvars.ContextVar = contextvars.ContextVar("abi_sandbox_caller", default=None)


@contextmanager
def sandbox_caller(run_id: str, agent_card_path: Optional[str] = None):
    """Run the enclosed code as a sandbox caller for ``run_id``.

    ``agent_card_path`` is the card that signs the requests (default: the
    ``AGENT_CARD`` env var, the same card the agent uses for MCP calls).
    """
    if not run_id:
        raise ValueError("the sandbox requires a run_id")
    # No card is not an error here: the run is denied when it is sent
    # (run() below), so a caller on the docker backend is never affected.
    card = agent_card_path or os.getenv("AGENT_CARD")
    token = _caller.set({"run_id": run_id, "agent_card_path": card})
    try:
        yield
    finally:
        _caller.reset(token)


def current_caller() -> Optional[Dict[str, str]]:
    return _caller.get()


def request_digest(run_id: str, files: Dict[str, bytes], command: List[str],
                   image: str, env: Dict[str, str], limits: Dict) -> str:
    """What the caller signs and the service recomputes."""
    canonical = {
        "run_id": run_id,
        "command": list(command),
        "image": image,
        "env": dict(sorted((env or {}).items())),
        "limits": dict(sorted(limits.items())),
        "files": {name: hashlib.sha256(_bytes(body)).hexdigest() for name, body in sorted(files.items())},
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bytes(body) -> bytes:
    return body.encode() if isinstance(body, str) else body


async def run(files: Dict[str, bytes], command: List[str], image: str,
              env: Dict[str, str], limits) -> "SandboxResult":
    """Send the run to sandbox-service. Never raises for a denial or a
    service failure: they come back as ``SandboxResult.error``, which the
    integration review treats as "could not run" (unverified), not as a pass."""
    import httpx
    from abi_core.common.sandbox import SandboxResult
    from abi_core.security.agent_auth import build_semantic_context_from_card

    caller = current_caller()
    if not caller:
        return SandboxResult(exit_code=None, error="sandbox denied: no run_id (call it inside @agent.sandboxed)")

    if not caller.get("agent_card_path"):
        return SandboxResult(exit_code=None, error="sandbox denied: no agent card to sign with (AGENT_CARD)")

    url = os.getenv("SANDBOX_SERVICE_URL", "").rstrip("/")
    if not url:
        return SandboxResult(exit_code=None, error="SANDBOX_SERVICE_URL is not set")

    limits_d = asdict(limits)
    digest = request_digest(caller["run_id"], files, command, image, env, limits_d)
    try:
        context = build_semantic_context_from_card(
            caller["agent_card_path"], tool_name=SANDBOX_ACTION, query=digest,
        )
    except Exception as e:
        return SandboxResult(exit_code=None, error=f"sandbox denied: cannot sign request ({e})")

    body = {
        "run_id": caller["run_id"],
        "caller_context": {"headers": context["headers"], "payload": context["payload"]},
        "files": {name: base64.b64encode(_bytes(b)).decode() for name, b in files.items()},
        "command": list(command),
        "image": image,
        "env": env,
        "limits": limits_d,
    }
    try:
        async with httpx.AsyncClient(timeout=limits.timeout_s + 120) as client:
            response = await client.post(f"{url}/run", json=body)
        data = response.json()
    except Exception as e:
        return SandboxResult(exit_code=None, error=f"sandbox-service unreachable: {type(e).__name__}: {e}")

    if not data.get("allowed"):
        return SandboxResult(exit_code=None, error=f"sandbox denied: {data.get('reason') or 'no reason given'}")
    result = data.get("result") or {}
    fields = SandboxResult.__dataclass_fields__
    return SandboxResult(**{k: v for k, v in result.items() if k in fields})
