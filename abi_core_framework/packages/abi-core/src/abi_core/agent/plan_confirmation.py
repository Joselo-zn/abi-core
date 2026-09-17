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

# Default message for the "plan_confirmation_orphaned" classification —
# exported so every caller shows the same wording instead of each writing
# its own; override freely if a caller wants something more specific.
ORPHANED_CONFIRMATION_MESSAGE = (
    "I don't have a plan waiting for confirmation in this session. "
    "This can happen if session continuity was lost between requests "
    "(e.g. no session token). What would you like me to do?"
)


def classify_plan_confirmation_sentinel(
    query: str, session_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Fast, sync, zero-LLM check: is `query` one of the fixed UI sentinels?

    Extracted from `classify_plan_confirmation_reply` (2026-08 orchestrator
    tool-call routing redesign) so a caller that no longer wants the LLM
    free-text interpretation path (e.g. the Orchestrator's reasoning turn,
    which now delegates that to an LLM tool call instead) can still reuse
    the exact same sentinel logic. `classify_plan_confirmation_reply` itself
    calls this first — behavior for existing callers (haiku, any standalone
    agent) is unchanged.

    Returns ``None`` if `query` isn't one of the three sentinels.
    """
    pending_plan = session_context.get("pending_plan")

    if query == PLAN_CONFIRM_APPROVE:
        if not pending_plan:
            return {"classification": "plan_confirmation_orphaned", "query": query}
        return {"classification": "plan_confirmed", "pending_plan": pending_plan}

    if query == PLAN_CONFIRM_REJECT:
        if not pending_plan:
            return {"classification": "plan_confirmation_orphaned", "query": query}
        return {"classification": "plan_rejected"}

    if query == PLAN_CONFIRM_MODIFY:
        if not pending_plan:
            return {"classification": "plan_confirmation_orphaned", "query": query}
        return {"classification": "plan_modify_requested", "pending_plan": pending_plan}

    return None


async def classify_plan_confirmation_reply(
    query: str,
    session_context: Dict[str, Any],
    llm_config: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Determine whether `query` is a reply to a pending plan confirmation.

    Returns ``None`` if `query` doesn't look like a confirmation reply at
    all — the caller should fall through to its normal handling (treat it
    as a new request). Otherwise returns one of:

        {"classification": "plan_confirmed", "pending_plan": <dict>}
        {"classification": "plan_rejected"}
        {"classification": "plan_modify_requested", "pending_plan": <dict>}
        {"classification": "plan_modify_feedback",
         "original_query": <str>, "feedback": <str>}
        {"classification": "plan_confirmation_orphaned", "query": <str>}

    Two fast paths need no LLM call: the fixed UI sentinels
    (``PLAN_CONFIRM_APPROVE``/``REJECT``/``MODIFY``, exact string match —
    language-agnostic technical strings a button sends), and a reply that
    arrives while ``awaiting_plan_modification`` is set (already asked "what
    would you like to change", so this reply IS the feedback verbatim, no
    need to re-interpret intent). Everything else — free text, any
    language/phrasing — is interpreted by the LLM (see
    ``_interpret_confirmation_reply``) instead of matched against a
    hardcoded word list, so "yes", "sí", "looks good", "está perfecto" all
    work the same way, and "no, hazlo más corto" gives you the reject *and*
    the feedback in one turn instead of requiring two round-trips.

    ``plan_confirmation_orphaned`` fires when a sentinel arrives but there's
    no ``pending_plan`` in `session_context` to apply it to — most commonly
    because the caller lost session continuity (e.g. a raw request with no
    session token, so each call lands in a fresh anonymous context — see
    docs/single-agent/07-sessions-multi-turn.md). Silently falling through
    here is what used to happen, and it's a bad failure mode: the bare word
    "aprobado" would get planned as if it were the actual request. Callers
    should respond with a clear message instead of guessing.
    """
    pending_plan = session_context.get("pending_plan")

    sentinel_result = classify_plan_confirmation_sentinel(query, session_context)
    if sentinel_result is not None:
        return sentinel_result

    if not pending_plan:
        return None

    if session_context.get("awaiting_plan_modification"):
        return {
            "classification": "plan_modify_feedback",
            "original_query": session_context.get("pending_plan_query", ""),
            "feedback": query,
        }

    decision, feedback = await _interpret_confirmation_reply(
        query, pending_plan, llm_config, session_id=session_id
    )
    if decision == "approve":
        return {"classification": "plan_confirmed", "pending_plan": pending_plan}
    if decision == "reject":
        return {"classification": "plan_rejected"}
    if decision == "modify":
        if feedback:
            return {
                "classification": "plan_modify_feedback",
                "original_query": session_context.get("pending_plan_query", ""),
                "feedback": feedback,
            }
        return {"classification": "plan_modify_requested", "pending_plan": pending_plan}

    abi_logging(
        "[⚠️] Pending plan exists but reply doesn't look like a confirmation "
        "(LLM decision: unrelated/unparseable) — falling through to normal handling",
        level="debug",
    )
    return None


async def _interpret_confirmation_reply(
    query: str,
    pending_plan: Dict[str, Any],
    llm_config: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
) -> tuple:
    """Best-effort LLM interpretation of a free-text confirmation reply.

    Any failure (LLM error, unparseable response, invalid decision) returns
    ``(None, "")`` — the caller then treats the reply as a new request,
    exactly like today's "didn't match anything" fallback. Deliberately
    never guesses "approve" on failure — that would be dangerous.
    """
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.prompts import build_plan_confirmation_interpretation_prompt
    from abi_core.common.utils import clean_llm_json, format_plan_summary

    try:
        plan_summary = format_plan_summary(pending_plan)
        raw = await invoke(
            llm_config,
            build_plan_confirmation_interpretation_prompt(plan_summary, query),
            thread_id=session_id,
        )
        parsed = clean_llm_json(raw)
        decision = parsed.get("decision")
        if decision not in ("approve", "reject", "modify", "unrelated"):
            abi_logging(f"[⚠️] Unrecognized plan-confirmation decision '{decision}'", level="warning")
            return None, ""
        return decision, (parsed.get("feedback") or "").strip()
    except Exception as e:  # noqa: BLE001 — best-effort, never blocks the reply
        abi_logging(f"[⚠️] Plan-confirmation interpretation failed: {e}", level="warning")
        return None, ""


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
