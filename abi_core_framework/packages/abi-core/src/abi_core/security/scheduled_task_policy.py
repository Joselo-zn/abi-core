"""
abi_core.security.scheduled_task_policy — OPA governance gate for
`@agent.task_schedule`.

Direct OPA POST, shaped like `A2AAccessValidator` — NOT the heavier
Guardian-agent-via-A2A-discovery path (`orchestrator.steps.guardian_validate`),
which needs the semantic layer AND a running Guardian agent, a much heavier
prerequisite than "OPA is reachable".

Fail-open by default (diverges from Guardian's own always-fail-closed
`SecurePolicyEngine`) — see
.abi/tsd/2026-08-02-scheduled-task-opa-fail-open.md for the full reasoning:
OPA/Guardian are optional per-project (`--with-guardian`), so gating a
project's own recurring job on infrastructure it may never have provisioned
would silently and permanently break every `@agent.task_schedule` the moment
OPA is unreachable. This follows the same graceful-degradation precedent
already established for other optional infra (`abi_core.memory`, the
semantic layer).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from abi_core.common.async_task_store import log_task_event
from abi_core.common.utils import abi_logging

_DEFAULT_BUNDLE_PATH = "abi/scheduled_task/allow"
_DEFAULT_TIMEOUT = 5.0


async def check_scheduled_task_policy(
    agent_name: str,
    task_name: str,
    trigger: str,
    *,
    opa_url: Optional[str] = None,
    bundle_path: str = _DEFAULT_BUNDLE_PATH,
    fail_mode: str = "open",
    timeout: float = _DEFAULT_TIMEOUT,
) -> Tuple[bool, str]:
    """Ask OPA "is this agent allowed to run this scheduled task right now?"

    POSTs ``{opa_url}/v1/data/{bundle_path}`` with
    ``{"input": {agent_name, task_name, trigger, timestamp}}``. Never raises
    — every path (OPA not configured, non-200, timeout, other exception,
    success) is logged via ``log_task_event`` so the allow/deny decision
    itself is auditable without a new persistence layer.

    Returns ``(allowed, reason)``. When OPA isn't configured/reachable:
    ``fail_mode="open"`` (default) allows with a logged warning;
    ``fail_mode="closed"`` denies — pass this explicitly for a project that
    wants this specific gate to fail closed like Guardian's own policy engine.
    """
    resolved_opa_url = opa_url or os.getenv("OPA_URL")
    context = {
        "agent_name": agent_name,
        "task_name": task_name,
        "trigger": trigger,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not resolved_opa_url:
        allowed = fail_mode != "closed"
        reason = "OPA_URL not configured"
        abi_logging(
            f"[⏰] Scheduled task '{task_name}': OPA not configured — "
            f"{'allowing' if allowed else 'denying'} (fail_mode={fail_mode})",
            level="warning",
        )
        log_task_event(
            "task_schedule_policy_check", task_name=task_name, async_task_id="-",
            status="allowed" if allowed else "denied", error=reason,
        )
        return allowed, reason

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{resolved_opa_url}/v1/data/{bundle_path}",
                json={"input": context},
            )
            if response.status_code != 200:
                reason = f"OPA returned status {response.status_code}"
                allowed = fail_mode != "closed"
                abi_logging(f"[⏰] Scheduled task '{task_name}': {reason}", level="error")
                log_task_event(
                    "task_schedule_policy_check", task_name=task_name, async_task_id="-",
                    status="allowed" if allowed else "denied", error=reason,
                )
                return allowed, reason

            result = response.json()
            allowed = bool(result.get("result", False))
            reason = "" if allowed else "Denied by scheduled_task policy"
            abi_logging(
                f"[⏰] Scheduled task '{task_name}': "
                f"{'✅ allowed' if allowed else f'❌ denied ({reason})'} by OPA",
            )
            log_task_event(
                "task_schedule_policy_check", task_name=task_name, async_task_id="-",
                status="allowed" if allowed else "denied", error=reason or None,
            )
            return allowed, reason

    except httpx.TimeoutException:
        reason = "OPA request timeout"
        allowed = fail_mode != "closed"
        abi_logging(f"[⏰] Scheduled task '{task_name}': {reason}", level="error")
        log_task_event(
            "task_schedule_policy_check", task_name=task_name, async_task_id="-",
            status="allowed" if allowed else "denied", error=reason,
        )
        return allowed, reason

    except Exception as e:  # noqa: BLE001 — never block a scheduled firing on this
        reason = f"Policy check error: {e}"
        allowed = fail_mode != "closed"
        abi_logging(f"[⏰] Scheduled task '{task_name}': {reason}", level="error")
        log_task_event(
            "task_schedule_policy_check", task_name=task_name, async_task_id="-",
            status="allowed" if allowed else "denied", error=reason,
        )
        return allowed, reason
