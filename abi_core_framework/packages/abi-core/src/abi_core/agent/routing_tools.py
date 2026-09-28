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

from typing import Literal, Optional, Type, Union

from pydantic import BaseModel, Field, create_model

# Redesigned (2026-09-22, see
# .abi/specs/routing-decision-discriminated-union.md) from a single flat
# model merging every action's fields as simultaneously-visible optionals —
# live-confirmed to let the model write real content into the wrong field
# (e.g. action=answer_directly but the reply landed in `objective`, leaving
# `text` empty) because nothing at the schema level made that impossible,
# only the field descriptions argued against it. A discriminated union makes
# it structurally impossible instead: whichever action-branch the model
# picks, the OTHER branches' fields don't exist in that branch at all.
#
# Verified live against qwen3:latest (2026-09-22): a bare `Union[...]` as
# the schema root binds without error but fails at ainvoke() time
# ("TypeError: ... is not a module, class, method, or function") — the
# union must be a field on a real BaseModel wrapper, not the schema root
# itself. Field name is `outcome`, not `decision` — `resolve_pending_plan`'s
# own sub-field is already named `decision` (approve/reject/modify); naming
# the wrapper field the same would make it `result.decision.decision`.


class _CreatePlanDecision(BaseModel):
    action: Literal["create_plan"]
    objective: str = Field(description=(
        "The task objective to delegate, self-contained — a downstream "
        "planner with NO access to this conversation will read only this "
        "field. Start from the user's message, but pull in any concrete "
        "detail from '[SYSTEM STATE] Recent conversation' above that the "
        "current message depends on (place, dates, constraints already "
        "given) — do not make the planner ask again for something the user "
        "already said. Do not include meta-commentary or your own prior "
        "response."
    ))


class _ResolvePendingPlanDecision(BaseModel):
    action: Literal["resolve_pending_plan"]
    decision: Optional[Literal["approve", "reject", "modify"]] = Field(
        default=None,
        description=(
            "approve, reject, or modify — based on what the user's message "
            "says about the pending plan."
        ),
    )
    feedback: str = Field(default="", description="If decision=modify, the requested changes.")


class _ResolvePendingClarificationDecision(BaseModel):
    action: Literal["resolve_pending_clarification"]
    answer: str = Field(description="The user's answer to the pending clarification question.")


class _AnswerDirectlyDecision(BaseModel):
    action: Literal["answer_directly"]
    text: str = Field(description="Your full, direct reply to the user.")


_ACTION_MODELS: dict[str, Type[BaseModel]] = {
    "create_plan": _CreatePlanDecision,
    "resolve_pending_plan": _ResolvePendingPlanDecision,
    "resolve_pending_clarification": _ResolvePendingClarificationDecision,
    "answer_directly": _AnswerDirectlyDecision,
}


def build_routing_decision_schema(valid_actions: list[str]) -> Type[BaseModel]:
    """Build a wrapper model whose `outcome` field is a discriminated union
    of the per-action decision models for `valid_actions` (or, in the
    single-action case — not observed in production today, see
    steps.py::build_routing_contract, but handled defensively — just that
    one model directly, since Union needs 2+ members). Used with
    `ChatOllama.with_structured_output(schema, method="json_schema")` to
    force an explicit, schema-valid choice where the chosen action's own
    field is the ONLY place its content can go.
    """
    members = tuple(_ACTION_MODELS[a] for a in valid_actions)
    if len(members) == 1:
        outcome_field = (members[0], Field(...))
    else:
        outcome_field = (Union[members], Field(discriminator="action"))
    return create_model("RoutingDecisionWrapper", outcome=outcome_field)


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
