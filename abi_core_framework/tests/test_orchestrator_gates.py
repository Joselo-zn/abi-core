"""
Deterministic gates of the Orchestrator: the routing contract and schema
(which actions a turn may take) and Phase 2.5 (which tasks missed their file
deliverable and what has to be rebuilt with them). No LLM involved.
Plan: .abi/specs/not-implemented/testing-plan.md (step 4).
"""

import importlib
import sys
import types

import pytest
from a2a.types import Artifact, Part, StreamResponse, TaskArtifactUpdateEvent
from google.protobuf import struct_pb2
from pydantic import ValidationError

from abi_core.agent.routing_tools import build_routing_decision_schema


def _orchestrator_steps():
    """Load the Orchestrator's steps.py with stand-in `app` and `config`
    modules (it imports them as loose files inside its container)."""
    class _Agent:
        def step(self, *a, **k):
            return lambda fn: fn
    sys.modules["app"] = types.SimpleNamespace(agent=_Agent())
    sys.modules["config"] = types.SimpleNamespace(AGENT_CARD=None, config=types.SimpleNamespace())
    try:
        return importlib.import_module("abi_agents.orchestrator.agent.steps")
    finally:
        sys.modules.pop("app", None)
        sys.modules.pop("config", None)


steps = _orchestrator_steps()


# ── Routing contract: which actions each turn may take ──────────────────

class TestRoutingContract:
    def test_fresh_turn_can_plan_or_answer(self):
        contract = steps.build_routing_contract("make a snake game", {}, {})
        assert contract["valid_actions"] == ["create_plan", "answer_directly"]
        assert contract["query"] == "make a snake game"
        assert contract["pending_plan_summary"] is None
        assert contract["pending_clarification_question"] is None

    def test_pending_plan_only_allows_resolving_it(self):
        ctx = {"pending_plan": {"tasks": [{"task_id": "t1", "description": "write main.py"}]}}
        contract = steps.build_routing_contract("dale", ctx, {})
        assert contract["valid_actions"] == ["resolve_pending_plan"]
        assert contract["pending_plan_summary"]

    def test_pending_clarification_can_be_answered_or_bypassed(self):
        contract = steps.build_routing_contract("blue", {}, {"clarification": "Which color?"})
        assert contract["valid_actions"] == ["resolve_pending_clarification", "answer_directly"]
        assert contract["pending_clarification_question"] == "Which color?"

    def test_pending_plan_wins_over_pending_clarification(self):
        ctx = {"pending_plan": {"tasks": []}}
        contract = steps.build_routing_contract("ok", ctx, {"clarification": "Which color?"})
        assert contract["valid_actions"] == ["resolve_pending_plan"]

    def test_last_error_and_conversation_reach_the_contract(self):
        ctx = {"last_error": "Builder timed out",
               "conversation_summary": [{"user": "hola", "assistant": "¿qué hacemos?"}]}
        contract = steps.build_routing_contract("y ahora?", ctx, {})
        assert contract["recent_error_summary"] == "Builder timed out"
        assert contract["recent_conversation_summary"] == "User: hola\nAssistant: ¿qué hacemos?"


# ── Routing schema: the model can only answer within the contract ───────

class TestRoutingDecisionSchema:
    schema = build_routing_decision_schema(["create_plan", "answer_directly"])

    def test_each_valid_action_parses_into_its_own_branch(self):
        plan = self.schema.model_validate({"outcome": {"action": "create_plan", "objective": "snake game"}})
        assert plan.outcome.action == "create_plan" and plan.outcome.objective == "snake game"
        reply = self.schema.model_validate({"outcome": {"action": "answer_directly", "text": "hola"}})
        assert reply.outcome.text == "hola"

    def test_action_outside_the_contract_is_rejected(self):
        with pytest.raises(ValidationError):
            self.schema.model_validate({"outcome": {"action": "resolve_pending_plan", "decision": "approve"}})

    def test_content_in_another_branchs_field_is_rejected(self):
        # answer_directly with the reply written into `objective` (seen live,
        # 2026-09-22): the branch requires `text`, so it cannot validate.
        with pytest.raises(ValidationError):
            self.schema.model_validate({"outcome": {"action": "answer_directly", "objective": "hola"}})

    def test_json_schema_offers_only_the_valid_actions(self):
        js = self.schema.model_json_schema()
        actions = {d["properties"]["action"]["const"] for d in js["$defs"].values() if "action" in d.get("properties", {})}
        assert actions == {"create_plan", "answer_directly"}

    def test_single_action_contract(self):
        schema = build_routing_decision_schema(["resolve_pending_plan"])
        out = schema.model_validate({"outcome": {"action": "resolve_pending_plan", "decision": "modify",
                                                 "feedback": "shorter"}})
        assert (out.outcome.decision, out.outcome.feedback) == ("modify", "shorter")
        with pytest.raises(ValidationError):
            schema.model_validate({"outcome": {"action": "resolve_pending_plan", "decision": "maybe"}})
        with pytest.raises(ValidationError):
            schema.model_validate({"outcome": {"action": "answer_directly", "text": "hola"}})

    def test_contract_actions_build_a_schema(self):
        for ctx, clar in (({}, {}), ({"pending_plan": {"tasks": []}}, {}), ({}, {"clarification": "?"})):
            actions = steps.build_routing_contract("q", ctx, clar)["valid_actions"]
            assert build_routing_decision_schema(actions).model_fields["outcome"]


# ── Phase 2.5: file deliverables and what a rebuild invalidates ─────────

def _chunk(agent, filename):
    """A real A2A artifact chunk carrying one uploaded artifact."""
    data = struct_pb2.Value()
    data.struct_value.update({"uploaded_artifacts": [{"agent": agent, "filename": filename}]})
    return StreamResponse(artifact_update=TaskArtifactUpdateEvent(artifact=Artifact(parts=[Part(data=data)])))


def _node(agent_name):
    return types.SimpleNamespace(target_agent_card=types.SimpleNamespace(name=agent_name))


def _file_task(tid, tag, deps=()):
    return {"task_id": tid, "target": {"type": "file", "tag": tag}, "dependencies": list(deps)}


class TestDeliverableContracts:
    def test_task_that_uploaded_its_file_passes(self):
        tasks = [_file_task("t1", "main.py")]
        assert steps.check_deliverable_contracts(tasks, {"t1": _node("eph-1")}, [_chunk("eph-1", "main.py")]) == []

    def test_task_without_its_file_fails(self):
        tasks = [_file_task("t1", "main.py")]
        assert steps.check_deliverable_contracts(tasks, {"t1": _node("eph-1")}, [_chunk("eph-1", "other.py")]) == ["t1"]

    def test_file_uploaded_by_another_task_does_not_count(self):
        tasks = [_file_task("t1", "main.py"), _file_task("t2", "game.py")]
        nodes = {"t1": _node("eph-1"), "t2": _node("eph-2")}
        results = [_chunk("eph-2", "main.py"), _chunk("eph-2", "game.py")]
        assert steps.check_deliverable_contracts(tasks, nodes, results) == ["t1"]

    def test_task_without_a_file_target_is_not_checked(self):
        tasks = [{"task_id": "t1", "target": {"type": "agent", "tag": "x"}}, {"task_id": "t2"}]
        assert steps.check_deliverable_contracts(tasks, {}, []) == []

    def test_task_without_a_node_fails(self):
        assert steps.check_deliverable_contracts([_file_task("t1", "main.py")], {}, [_chunk("eph-1", "main.py")]) == ["t1"]

    def test_unparseable_results_are_ignored(self):
        tasks = [_file_task("t1", "main.py")]
        results = [object(), None, _chunk("eph-1", "main.py")]
        assert steps.check_deliverable_contracts(tasks, {"t1": _node("eph-1")}, results) == []


class TestTransitiveDependents:
    tasks = [
        {"task_id": "a"},
        {"task_id": "b", "dependencies": ["a"]},
        {"task_id": "c", "dependencies": ["b"]},
        {"task_id": "d"},
        {"task_id": "e", "dependencies": ["d", "c"]},
    ]

    def test_failed_tasks_and_everything_downstream(self):
        assert steps.transitive_dependents(["a"], self.tasks) == {"a", "b", "c", "e"}

    def test_independent_branch_untouched(self):
        assert steps.transitive_dependents(["d"], self.tasks) == {"d", "e"}

    def test_leaf_affects_only_itself(self):
        assert steps.transitive_dependents(["e"], self.tasks) == {"e"}

    def test_order_of_tasks_does_not_matter(self):
        assert steps.transitive_dependents(["a"], list(reversed(self.tasks))) == {"a", "b", "c", "e"}

    def test_nothing_failed(self):
        assert steps.transitive_dependents([], self.tasks) == set()

    def test_cycle_terminates(self):
        cyclic = [{"task_id": "x", "dependencies": ["y"]}, {"task_id": "y", "dependencies": ["x"]},
                  {"task_id": "z", "dependencies": ["y"]}]
        assert steps.transitive_dependents(["x"], cyclic) == {"x", "y", "z"}
