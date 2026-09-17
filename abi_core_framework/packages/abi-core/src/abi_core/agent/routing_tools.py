"""
abi_core.agent.routing_tools — Build a forced-choice structured routing
decision instead of a rigid deterministic gate.

History: originally built on LangChain tool-calling with a routing tool per
action (`create_plan`, `resolve_pending_plan`, `resolve_pending_clarification`)
plus a probabilistic "did you mean to delegate?" second-guess
(`_should_have_delegated`/`_enforce_create_plan` in orchestrator.py) for the
case where the LLM produced no tool call at all. That second-guess broke in
production (see .abi/issues/2026-09-06-reasoning-antes-de-delegar.md) because
"no tool call" conflated two different things: "decided not to delegate"
(legitimate) vs. "failed to produce a tool call at all" (model reliability).

Redesigned (see .abi/specs/orchestrator-unified-routing-contract.md) around
structured output instead: a dynamic Pydantic schema whose `action` field is
a closed `Literal` of whatever actions are valid for this turn (computed
once, deterministically, by steps.py::build_routing_contract — not
duplicated here). `ChatOllama.with_structured_output(schema,
method="json_schema")` forces a JSON response matching that schema — there
is no "didn't choose" outcome at the schema level, so the ambiguity that
broke `_should_have_delegated` cannot occur.

Note: `tool_choice="required"` on LangChain tool-calling was the original
plan but is a documented no-op for Ollama (`ChatOllama.bind_tools`) —
verified against the installed langchain-ollama source before switching to
this approach.
"""

from __future__ import annotations

from typing import Literal, Optional, Type

from pydantic import BaseModel, Field, create_model

# Per-action optional fields merged into the dynamic schema. `action` itself
# is always added separately (its Literal choices come from valid_actions).
_ACTION_FIELDS: dict[str, dict[str, tuple]] = {
    "create_plan": {
        "objective": (
            str,
            Field(default="", description=(
                "REQUIRED when action=create_plan: the task objective to "
                "delegate, self-contained — a downstream planner with NO "
                "access to this conversation will read only this field. "
                "Start from the user's message, but pull in any concrete "
                "detail from '[SYSTEM STATE] Recent conversation' above "
                "that the current message depends on (place, dates, "
                "constraints already given) — do not make the planner ask "
                "again for something the user already said. Do not include "
                "meta-commentary or your own prior response."
            )),
        ),
    },
    "resolve_pending_plan": {
        "decision": (
            Optional[Literal["approve", "reject", "modify"]],
            Field(default=None, description=(
                "REQUIRED when action=resolve_pending_plan: approve, reject, "
                "or modify — based on what the user's message says about "
                "the pending plan."
            )),
        ),
        "feedback": (
            str,
            Field(default="", description="If decision=modify, the requested changes."),
        ),
    },
    "resolve_pending_clarification": {
        "answer": (
            str,
            Field(default="", description="The user's answer to the pending clarification question."),
        ),
    },
    "answer_directly": {
        "text": (
            str,
            Field(default="", description="The direct reply to send to the user."),
        ),
    },
}


def build_routing_decision_schema(valid_actions: list[str]) -> Type[BaseModel]:
    """Build a Pydantic model whose `action` field is a closed Literal of
    `valid_actions`, plus the union of optional fields relevant to those
    actions. Used with `ChatOllama.with_structured_output(schema,
    method="json_schema")` to force an explicit, schema-valid choice.
    """
    fields: dict[str, tuple] = {
        "action": (
            Literal[tuple(valid_actions)],
            Field(description="Which action to take, chosen from the allowed set for this turn."),
        )
    }
    for action in valid_actions:
        fields.update(_ACTION_FIELDS.get(action, {}))
    return create_model("RoutingDecision", **fields)


def format_system_state(
    pending_plan_summary: Optional[str],
    pending_clarification_question: Optional[str],
    recent_conversation_summary: Optional[str] = None,
) -> str:
    """Render the same [SYSTEM STATE] block the old inject_routing_state
    middleware used to inject into the system prompt — now passed explicitly
    into the phase-2 structured-output prompt instead of via middleware.

    ``recent_conversation_summary`` — see AbiAgent.record_conversation_turn /
    .abi/specs/orchestrator-conversation-memory.md — is the deterministic
    replacement for the (documented broken) discretionary memory-tool path;
    listed first since it's background context, not an outstanding decision
    like the other two blocks.
    """
    blocks = []
    if recent_conversation_summary:
        blocks.append(f"[SYSTEM STATE] Recent conversation:\n{recent_conversation_summary}")
    if pending_plan_summary:
        blocks.append(f"[SYSTEM STATE] Pending plan (awaiting approve/reject/modify):\n{pending_plan_summary}")
    if pending_clarification_question:
        blocks.append(f"[SYSTEM STATE] Unanswered clarification question:\n{pending_clarification_question}")
    return "\n\n".join(blocks)
