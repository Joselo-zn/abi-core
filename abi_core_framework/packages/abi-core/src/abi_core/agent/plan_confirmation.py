"""
abi_core.agent.plan_confirmation — Plan-approval state machine, extracted to
framework level.

Before 2026-08-03 this logic lived only inside `abi-agents/orchestrator`
(`steps.py::classify_query`'s pending-plan block, `orchestrator.py`'s
`_record_pending_plan`/`_clear_pending_plan`) — a standalone agent created
via `abi-core add agent` (not the swarm) had no way to ask the user to
approve/reject/modify a plan before executing it. Extracted verbatim (no
behavior change) because the classification is a pure function of `query` +
session context — no A2A, no Guardian, no semantic layer involved. See
.abi/tsd/2026-08-03-extract-plan-confirmation-methodology-to-abi-core.md.

What this module does NOT cover, on purpose: actually *executing* an
approved plan. That's caller-specific — the Orchestrator's answer is
`build_workflow` (spins up ephemeral agents via the Builder over A2A); a
single agent's answer is just looping over its own `execute_step` calls.
This module only owns the confirm/reject/modify decision and the session
bookkeeping around a pending plan.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from abi_core.common.utils import abi_logging

# Sentinel queries a UI sends when the user clicks a plan-confirmation action
# button (see abi-cli/scaffolding/ui/app.py.j2's @cl.action_callback). Single
# source of truth — callers (e.g. the Orchestrator) import these instead of
# redefining them.
PLAN_CONFIRM_APPROVE = "__plan_confirm_approve__"
PLAN_CONFIRM_REJECT = "__plan_confirm_reject__"
PLAN_CONFIRM_MODIFY = "__plan_confirm_modify__"

# Type alias for the session-context update callable a caller passes in —
# `AbiCore.update_session_context` or `AbiAgent.update_session_context`.
UpdateContextFn = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


def classify_plan_confirmation_reply(
    query: str, session_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Determine whether `query` is a reply to a pending plan confirmation.

    Returns ``None`` if ``session_context`` has no ``pending_plan`` at all,
    OR if there's a pending plan but `query` doesn't match any known
    confirm/reject/modify signal — in both cases the caller should fall
    through to its normal handling (e.g. treat it as a new request).

    Otherwise returns one of:
        {"classification": "plan_confirmed", "pending_plan": <dict>}
        {"classification": "plan_rejected"}
        {"classification": "plan_modify_requested", "pending_plan": <dict>}
        {"classification": "plan_modify_feedback",
         "original_query": <str>, "feedback": <str>}

    Pure function — no I/O, no side effects. `context_id` isn't needed here
    (only for the caller's own logging); pass a pre-fetched session_context
    dict (e.g. from `get_session_context`/`get_context`).
    """
    pending_plan = session_context.get("pending_plan")
    if not pending_plan:
        return None

    normalized = query.strip().lower()

    if query == PLAN_CONFIRM_APPROVE or normalized in ("sí", "si", "yes", "aprobar", "aprobado", "confirmo"):
        return {"classification": "plan_confirmed", "pending_plan": pending_plan}

    if query == PLAN_CONFIRM_REJECT or normalized in ("no", "rechazar", "cancelar"):
        return {"classification": "plan_rejected"}

    if query == PLAN_CONFIRM_MODIFY:
        return {"classification": "plan_modify_requested", "pending_plan": pending_plan}

    if session_context.get("awaiting_plan_modification"):
        return {
            "classification": "plan_modify_feedback",
            "original_query": session_context.get("pending_plan_query", ""),
            "feedback": query,
        }

    abi_logging(
        "[⚠️] Pending plan exists but query doesn't match confirm/reject/modify — "
        "falling through to normal handling",
        level="debug",
    )
    return None


async def record_pending_plan(
    update_context_fn: UpdateContextFn,
    context_id: str,
    plan: Dict[str, Any],
    original_query: str,
) -> None:
    """Record a plan awaiting the user's approve/reject/modify decision.

    ``update_context_fn`` is duck-typed — pass `agent.update_session_context`
    (AbiCore passthrough, for a `@agent.task`) or `self.update_session_context`
    (AbiAgent method, for an agent's own `stream()` override). No ABC needed:
    both already share the same `(context_id, patch) -> dict` signature.
    """
    await update_context_fn(context_id, {
        "pending_plan": plan,
        "pending_plan_query": original_query,
        "awaiting_plan_modification": False,
    })
    abi_logging(f"[📝] Pending plan recorded for session {context_id}")


async def clear_pending_plan(update_context_fn: UpdateContextFn, context_id: str) -> None:
    """Clear a pending plan — call after it's approved, rejected, or replaced."""
    await update_context_fn(context_id, {
        "pending_plan": None,
        "pending_plan_query": None,
        "awaiting_plan_modification": False,
    })
