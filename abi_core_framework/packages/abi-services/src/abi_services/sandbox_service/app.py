"""
sandbox-service — the only component that runs generated code.

Every request goes through, in order, and is audited whatever the outcome:

1. The request is self-consistent: a signed payload is present (always
   required), it signs ``run_sandbox`` and this exact request (digest), and
   it is recent.
2. Who is calling: the semantic layer verifies the caller's HMAC signature
   against its card (``verify_caller``), and returns the card without
   secrets. The service authenticates there with its own ServiceCard.
3. The facts of the run: its plan exists, it has a Python entry point, how
   many runs it already used.
4. OPA decides (``abi/sandbox``). OPA unreachable or any error: denied.
5. Only then the sandbox runs, on SANDBOX_SERVICE_BACKEND: ``docker``
   (default, local) or ``cloudrun`` (Cloud Run Jobs, GCP).

Audit: one JSON line per request in projects/<run_id>/review/sandbox-audit.jsonl.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.5-governed-sandbox.md
"""

import asyncio
import base64
import json
import os
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import FastAPI, Request

from abi_core.common import project_store
from abi_core.common.sandbox import SandboxLimits, run_in_sandbox
from abi_core.common.sandbox_service_client import SANDBOX_ACTION, request_digest
from abi_core.common.utils import abi_logging

AUDIT_FILE = "sandbox-audit.jsonl"


def _settings() -> Dict[str, Any]:
    rounds = int(os.getenv("INTEGRATION_REPAIR_ROUNDS", "3"))
    return {
        "opa_url": os.getenv("OPA_URL", "").rstrip("/"),
        "opa_path": os.getenv("SANDBOX_OPA_PATH", "abi/sandbox"),
        "service_card": os.getenv("SANDBOX_SERVICE_CARD", "/app/service_cards/sandbox.json"),
        # The reviewer's initial review, plus the Orchestrator's verification
        # of each report: the first one and one per round sent back (02.4).
        "max_runs": int(os.getenv("SANDBOX_MAX_RUNS_PER_RUN_ID", str(2 + rounds))),
        "max_skew_s": int(os.getenv("SANDBOX_MAX_SKEW_S", "120")),
        "backend": sandbox_backend(),
    }


def sandbox_backend() -> str:
    """Where the service runs the code. Never "service": it would call itself."""
    backend = os.getenv("SANDBOX_SERVICE_BACKEND", "docker").strip().lower()
    if backend not in ("docker", "cloudrun"):
        raise ValueError(f"SANDBOX_SERVICE_BACKEND must be 'docker' or 'cloudrun', not {backend!r}")
    return backend


# ── 1. Request self-consistency ─────────────────────────────────

def check_request(body: Dict[str, Any], max_skew_s: int) -> Tuple[Optional[str], Dict[str, bytes]]:
    """Return (denial reason or None, decoded files)."""
    run_id = body.get("run_id")
    if not run_id:
        return "missing run_id", {}
    ctx = body.get("caller_context") or {}
    payload = ctx.get("payload")
    if not payload or not (ctx.get("headers") or {}).get("X-ABI-Signature"):
        return "missing signed payload", {}
    if payload.get("tool") != SANDBOX_ACTION:
        return f"signature is not for {SANDBOX_ACTION}", {}
    try:
        files = {name: base64.b64decode(b64, validate=True) for name, b64 in (body.get("files") or {}).items()}
    except Exception:
        return "files are not valid base64", {}
    digest = request_digest(run_id, files, body.get("command") or [], body.get("image") or "",
                            body.get("env") or {}, body.get("limits") or {})
    if payload.get("query") != digest:
        return "signature does not cover this request", files
    try:
        if abs(time.time() - float(payload.get("ts", 0))) > max_skew_s:
            return "stale signature", files
    except (TypeError, ValueError):
        return "invalid timestamp", files
    return None, files


# ── 2. Caller identity (semantic layer) ─────────────────────────

async def verify_caller(caller_context: Dict[str, Any], service_card_path: str) -> Dict[str, Any]:
    from abi_core.common.semantic_tools import MCPToolkit
    from abi_core.common.service_card import ServiceCard

    try:
        toolkit = MCPToolkit(service_card=ServiceCard.from_file(service_card_path))
        result = await toolkit.call("verify_caller", caller_context=caller_context)
    except Exception as e:
        return {"verified": False, "reason": f"semantic layer unreachable: {e}", "card": None}
    if not isinstance(result, dict) or "verified" not in result:
        return {"verified": False, "reason": f"unexpected verify_caller answer: {str(result)[:200]}", "card": None}
    return result


# ── 3. Facts of the run ─────────────────────────────────────────

async def run_facts(run_id: str) -> Dict[str, Any]:
    facts = {"plan_exists": False, "has_executable_code": False, "runs_used": 0}
    try:
        plan = await project_store.load_json(run_id, "plan", "plan.json")
        facts["plan_exists"] = True
        design = (plan.get("technical_design") or {}).get("files") or []
        facts["has_executable_code"] = any(
            f.get("role") == "entry_point" and str(f.get("filename", "")).endswith(".py") for f in design
        )
    except Exception:
        pass
    facts["runs_used"] = sum(1 for e in await _read_audit(run_id) if e.get("decision") == "allowed")
    return facts


def caller_facts(verification: Dict[str, Any]) -> Dict[str, Any]:
    card = verification.get("card") or {}
    security = card.get("security") or {}
    return {
        "verified": bool(verification.get("verified")),
        "id": card.get("id", ""),
        "name": card.get("name", ""),
        "ephemeral": bool(card.get("ephemeral", False)),
        "allowed_actions": list(security.get("allowed_actions") or []),
    }


# ── 4. Policy (fail-closed) ─────────────────────────────────────

async def ask_opa(opa_input: Dict[str, Any], opa_url: str, opa_path: str) -> Tuple[bool, str]:
    if not opa_url:
        return False, "OPA_URL not configured"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{opa_url}/v1/data/{opa_path}", json={"input": opa_input})
        if response.status_code != 200:
            return False, f"OPA returned status {response.status_code}"
        result = response.json().get("result") or {}
    except Exception as e:
        return False, f"OPA unreachable: {type(e).__name__}"
    if result.get("allow") is True:
        return True, ""
    reasons = sorted(result.get("deny") or [])
    return False, "; ".join(reasons) or "denied by policy"


# ── Audit ───────────────────────────────────────────────────────

_audit_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _read_audit(run_id: str):
    try:
        raw = await project_store.load(run_id, "review", AUDIT_FILE)
    except Exception:
        return []
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


async def audit(run_id: str, entry: Dict[str, Any]) -> None:
    """Append one line. The object store has no append: read, add, write —
    serialized per run inside this (single) service process."""
    if not run_id:
        abi_logging(f"[🧪] sandbox request without run_id: {entry}", level="warning")
        return
    entry = {"at": datetime.now(timezone.utc).isoformat(), **entry}
    async with _audit_locks[run_id]:
        lines = [json.dumps(e, ensure_ascii=False) for e in await _read_audit(run_id)]
        lines.append(json.dumps(entry, ensure_ascii=False))
        try:
            await project_store.save(run_id, "review", AUDIT_FILE, ("\n".join(lines) + "\n").encode("utf-8"),
                                     metadata={"origin": "sandbox-service"})
        except Exception as e:
            abi_logging(f"[⚠️] sandbox audit not written for {run_id}: {e}", level="warning")


# ── The endpoint ────────────────────────────────────────────────

async def handle_run(body: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _settings()
    run_id = str(body.get("run_id") or "")
    request = {"command": body.get("command"), "image": body.get("image"),
               "files": sorted((body.get("files") or {}).keys())}
    claimed = ((body.get("caller_context") or {}).get("payload") or {}).get("agent_id", "")

    async def deny(reason: str, caller: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        abi_logging(f"[🧪] sandbox DENIED run={run_id} caller={claimed}: {reason}", level="warning")
        await audit(run_id, {"decision": "denied", "reason": reason, "caller_claimed": claimed,
                             "caller": caller, "request": request})
        return {"allowed": False, "reason": reason}

    reason, files = check_request(body, cfg["max_skew_s"])
    if reason:
        return await deny(reason)

    verification = await verify_caller(body["caller_context"], cfg["service_card"])
    caller = caller_facts(verification)
    if not caller["verified"]:
        return await deny(f"caller not verified: {verification.get('reason', '')}", caller)

    facts = await run_facts(run_id)
    opa_input = {
        "action": SANDBOX_ACTION,
        "run_id": run_id,
        "caller": caller,
        "run": facts,
        "limits": {"max_runs": cfg["max_runs"]},
        "request": {"command": body.get("command"), "image": body.get("image")},
    }
    allowed, reason = await ask_opa(opa_input, cfg["opa_url"], cfg["opa_path"])
    if not allowed:
        return await deny(reason, caller)

    try:
        limits = SandboxLimits(**(body.get("limits") or {}))
        # Explicit backend, whatever SANDBOX_RUNTIME says: "service" would call itself.
        result = await run_in_sandbox(files, body["command"], image=body["image"],
                                      env=body.get("env") or {}, limits=limits, backend=cfg["backend"])
    except Exception as e:
        return await deny(f"invalid request: {type(e).__name__}: {e}", caller)

    summary = {"exit_code": result.exit_code, "timed_out": result.timed_out,
               "oom_killed": result.oom_killed, "duration_s": round(result.duration_s, 2),
               "error": result.error}
    abi_logging(f"[🧪] sandbox ran run={run_id} caller={caller['id']}: {summary}")
    await audit(run_id, {"decision": "allowed", "caller": caller, "request": request, "result": summary})
    return {"allowed": True, "reason": "", "result": asdict(result)}


def create_app() -> FastAPI:
    app = FastAPI(title="abi sandbox-service")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/run")
    async def run(request: Request):
        try:
            body = await request.json()
        except Exception:
            return {"allowed": False, "reason": "body is not JSON"}
        return await handle_run(body if isinstance(body, dict) else {})

    return app
