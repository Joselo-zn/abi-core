"""
Plan confirmation (abi_core.agent.plan_confirmation): the UI sentinels, the
free-text reply interpreted by the LLM (faked here), and the pending-plan
bookkeeping. The modify-with-feedback sentinel is in test_plan_review.py.
Plan: .abi/specs/not-implemented/testing-plan.md (step 4).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import abi_core.agent.llm_provider as llm_provider
from abi_core.agent.plan_confirmation import (
    PLAN_CONFIRM_APPROVE,
    PLAN_CONFIRM_MODIFY,
    PLAN_CONFIRM_REJECT,
    _ConfirmationDecision,
    classify_plan_confirmation_reply,
    classify_plan_confirmation_sentinel,
    clear_pending_plan,
    record_pending_plan,
)

PLAN = {"tasks": [{"task_id": "t1", "description": "write main.py"}]}
PENDING = {"pending_plan": PLAN, "pending_plan_query": "make a snake game"}


def _reply(query, ctx, llm=None):
    """classify_plan_confirmation_reply with invoke_structured faked; returns
    (result, the fake) so a test can check whether the LLM was asked."""
    fake = llm or AsyncMock()
    with patch.object(llm_provider, "invoke_structured", fake):
        return asyncio.run(classify_plan_confirmation_reply(query, ctx, {"model": "fake"})), fake


def _llm_says(decision, feedback=""):
    return AsyncMock(return_value=_ConfirmationDecision(decision=decision, feedback=feedback))


class TestSentinels:
    @pytest.mark.parametrize("sentinel, expected", [
        (PLAN_CONFIRM_APPROVE, {"classification": "plan_confirmed", "pending_plan": PLAN}),
        (PLAN_CONFIRM_REJECT, {"classification": "plan_rejected"}),
        (PLAN_CONFIRM_MODIFY, {"classification": "plan_modify_requested", "pending_plan": PLAN}),
    ])
    def test_button_with_a_pending_plan(self, sentinel, expected):
        assert classify_plan_confirmation_sentinel(sentinel, PENDING) == expected

    @pytest.mark.parametrize("sentinel", [PLAN_CONFIRM_APPROVE, PLAN_CONFIRM_REJECT, PLAN_CONFIRM_MODIFY])
    def test_button_without_a_pending_plan_is_orphaned(self, sentinel):
        assert classify_plan_confirmation_sentinel(sentinel, {}) == {
            "classification": "plan_confirmation_orphaned", "query": sentinel}

    def test_free_text_is_not_a_sentinel(self):
        assert classify_plan_confirmation_sentinel("approve", PENDING) is None

    def test_reply_uses_the_sentinel_without_the_llm(self):
        result, llm = _reply(PLAN_CONFIRM_APPROVE, PENDING)
        assert result["classification"] == "plan_confirmed"
        llm.assert_not_awaited()


class TestFreeTextReply:
    def test_no_pending_plan_is_a_new_request(self):
        result, llm = _reply("make a snake game", {})
        assert result is None
        llm.assert_not_awaited()

    def test_awaited_modification_is_the_feedback_verbatim(self):
        ctx = dict(PENDING, awaiting_plan_modification=True)
        result, llm = _reply("use pygame", ctx)
        llm.assert_not_awaited()
        assert result == {"classification": "plan_modify_feedback",
                          "original_query": "make a snake game", "feedback": "use pygame"}

    def test_approval(self):
        result, llm = _reply("dale, se ve bien", PENDING, _llm_says("approve"))
        assert result == {"classification": "plan_confirmed", "pending_plan": PLAN}
        llm.assert_awaited_once()

    def test_rejection(self):
        result, _ = _reply("no, olvídalo", PENDING, _llm_says("reject"))
        assert result == {"classification": "plan_rejected"}

    def test_modification_with_the_change(self):
        result, _ = _reply("hazlo más corto", PENDING, _llm_says("modify", "  shorter  "))
        assert result == {"classification": "plan_modify_feedback",
                          "original_query": "make a snake game", "feedback": "shorter"}

    def test_modification_without_the_change_asks_for_it(self):
        result, _ = _reply("quiero cambiar algo", PENDING, _llm_says("modify"))
        assert result == {"classification": "plan_modify_requested", "pending_plan": PLAN}

    def test_unrelated_reply_falls_through(self):
        result, _ = _reply("¿qué hora es?", PENDING, _llm_says("unrelated"))
        assert result is None

    def test_llm_failure_never_approves(self):
        result, _ = _reply("sí", PENDING, AsyncMock(side_effect=RuntimeError("ollama down")))
        assert result is None

    def test_llm_gets_the_plan_and_the_reply(self):
        _, llm = _reply("sí", PENDING, _llm_says("approve"))
        config, prompt, schema = llm.await_args.args
        assert config == {"model": "fake"} and schema is _ConfirmationDecision
        assert "sí" in prompt and "write main.py" in prompt


class TestPendingPlanBookkeeping:
    def test_record_and_clear(self):
        updates = []

        async def update(context_id, patch):
            updates.append((context_id, patch))
            return patch

        asyncio.run(record_pending_plan(update, "ctx-1", PLAN, "make a snake game"))
        asyncio.run(clear_pending_plan(update, "ctx-1"))
        assert updates == [
            ("ctx-1", {"pending_plan": PLAN, "pending_plan_query": "make a snake game",
                       "awaiting_plan_modification": False}),
            ("ctx-1", {"pending_plan": None, "pending_plan_query": None,
                       "awaiting_plan_modification": False}),
        ]
