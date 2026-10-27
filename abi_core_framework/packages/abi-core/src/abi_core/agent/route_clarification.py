"""
The routing's follow-up question ("is X what you want?") — the contract
between whoever asks it and the UI that shows it.

An agent asks with::

    AgentResponse.input_required(
        fallback_text,                       # question + numbered options, for clients without a UI
        action_type=ROUTE_CLARIFICATION_ACTION,
        clarify={
            "clarify_id": "c-7f3a",
            "question_key": "plan_reply.approve", "params": {},
            "original_message": "dale nomás",
            "mode": "guess",                 # or "neutral" (no guess: low signal or a failure)
            "options": [
                {"id": "approve", "label_key": "plan.approve", "kind": "choice", "primary": True},
                {"id": "modify", "label_key": "plan.modify", "kind": "text"},
                {"id": "reject", "label_key": "plan.reject", "kind": "choice"},
                {"id": "other", "label_key": "route.unrelated", "kind": "link"},
            ],
        },
    )

Texts travel as keys (+ ``params``, globally or per option) so the UI shows
them in its own language. The user's choice comes back as the JSON sentinel
``{"_sentinel": ROUTE_CLARIFY_SENTINEL, "clarify_id", "option", "text"?}``,
which the asker resolves by code, never through a model. Which questions
are asked, and what each option does, belongs to the asker. Spec:
.abi/specs/not-implemented/ux/routing-clarification-ui.md.
"""

ROUTE_CLARIFICATION_ACTION = "route_clarification"
ROUTE_CLARIFY_SENTINEL = "__route_clarify__"
