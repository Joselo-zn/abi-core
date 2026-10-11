"""
Tests for the plan review card's deterministic parts: execution order,
build_plan_view(), PlanTask.title, the modify-with-feedback sentinel and
the cleaned-up text summary.
"""

import json

from abi_core.agent.plan_confirmation import (
    PLAN_MODIFY_FEEDBACK_SENTINEL,
    classify_plan_confirmation_sentinel,
)
from abi_core.common.plan_models import PlanTask
from abi_core.common.utils import build_plan_view, format_plan_summary, plan_execution_order


def _task(tid, deps=(), title=None, tag=None, desc=None):
    task = {
        "task_id": tid,
        "description": desc or f"Write a Python file named {tag or tid}.py that does {tid}",
        "dependencies": list(deps),
    }
    if title:
        task["title"] = title
    if tag:
        task["target"] = {"tag": tag, "type": "file"}
    return task


PACMAN = {
    "objective": "Pac-Man clone",
    "execution_strategy": "sequential",
    "methodology": "Agile (Scrum/Kanban)",
    "methodology_rationale": "Fixed framing for every plan — see PLANNER_COT_INSTRUCTIONS",
    "tasks": [
        _task("task_1", deps=["task_2", "task_3"], title="Juego principal", tag="main.py"),
        _task("task_2", title="Movimiento de Pac-Man", tag="player.py"),
        _task("task_3", deps=["task_2"], tag="ghosts.py",
              desc="Write a Python file named ghosts.py that implements ghost AI. Four ghosts."),
    ],
}


class TestExecutionOrder:
    def test_dependencies_first(self):
        order = [t["task_id"] for t in plan_execution_order(PACMAN["tasks"])]
        assert order == ["task_2", "task_3", "task_1"]

    def test_plan_order_kept_among_ready_tasks(self):
        tasks = [_task("task_3"), _task("task_1"), _task("task_2", deps=["task_3"])]
        assert [t["task_id"] for t in plan_execution_order(tasks)] == ["task_3", "task_1", "task_2"]

    def test_unknown_dependency_ignored(self):
        tasks = [_task("task_2", deps=["task_9"])]
        assert [t["task_id"] for t in plan_execution_order(tasks)] == ["task_2"]

    def test_cycle_keeps_everything(self):
        tasks = [_task("task_1", deps=["task_2"]), _task("task_2", deps=["task_1"])]
        assert [t["task_id"] for t in plan_execution_order(tasks)] == ["task_1", "task_2"]


class TestBuildPlanView:
    def test_steps_numbered_in_execution_order(self):
        view = build_plan_view(PACMAN)
        assert [(s["index"], s["task_id"]) for s in view["steps"]] == [
            (1, "task_2"), (2, "task_3"), (3, "task_1"),
        ]
        main = view["steps"][2]
        assert main["depends_on"] == [1, 2]
        assert main["title"] == "Juego principal"
        assert main["deliverable"] == {"tag": "main.py", "type": "file"}

    def test_fallback_title_strips_agent_lead_in(self):
        ghosts = build_plan_view(PACMAN)["steps"][1]
        assert ghosts["title"] == "Implements ghost AI"
        assert ghosts["detail"].startswith("Write a Python file named ghosts.py")

    def test_deliverables_and_no_internal_fields(self):
        view = build_plan_view(PACMAN)
        assert view["deliverables"] == ["player.py", "ghosts.py", "main.py"]
        dumped = json.dumps(view)
        assert "PLANNER_COT_INSTRUCTIONS" not in dumped
        assert "methodology" not in dumped

    def test_notice_only_for_models_to_download(self):
        status = {
            "task_1": {"model": "qwen3", "location": "http://ollama:11434"},
            "task_2": {"model": "devstral", "location": None},
            "task_3": {"model": "devstral", "location": None},
        }
        view = build_plan_view(PACMAN, status)
        assert view["notices"] == [{"code": "model_download", "model": "devstral"}]
        assert "ollama:11434" not in json.dumps(view)

    def test_assigned_agent_and_direct_tool(self):
        plan = {"objective": "x", "tasks": [
            {**_task("task_1", tag="a.py"), "agents": [{"name": "Writer Agent"}]},
            {**_task("task_2", tag="r.pdf"), "direct_tool": "write_pdf"},
        ]}
        steps = build_plan_view(plan)["steps"]
        assert steps[0]["agent"] == "Writer Agent"
        assert steps[1]["agent"] is None and steps[1]["direct_tool"] == "write_pdf"


class TestPlanTaskTitle:
    def test_long_title_trimmed_not_rejected(self):
        task = PlanTask(task_id="task_1", title="x" * 200, description="Write a file named a.py that works")
        assert len(task.title) == 60 and task.title.endswith("…")

    def test_blank_title_becomes_none(self):
        task = PlanTask(task_id="task_1", title="   ", description="Write a file named a.py that works")
        assert task.title is None

    def test_title_optional(self):
        assert PlanTask(task_id="task_1", description="Write a file named a.py that works").title is None


class TestModifyFeedbackSentinel:
    def _query(self, feedback):
        return json.dumps({"_sentinel": PLAN_MODIFY_FEEDBACK_SENTINEL, "feedback": feedback})

    def test_feedback_with_pending_plan(self):
        ctx = {"pending_plan": {"tasks": []}, "pending_plan_query": "pacman"}
        result = classify_plan_confirmation_sentinel(self._query("más rápido"), ctx)
        assert result == {
            "classification": "plan_modify_feedback",
            "original_query": "pacman",
            "feedback": "más rápido",
        }

    def test_orphaned_without_pending_plan(self):
        result = classify_plan_confirmation_sentinel(self._query("x"), {})
        assert result["classification"] == "plan_confirmation_orphaned"

    def test_empty_feedback_is_not_a_sentinel(self):
        assert classify_plan_confirmation_sentinel(self._query("  "), {"pending_plan": {}}) is None

    def test_plain_json_text_is_not_a_sentinel(self):
        assert classify_plan_confirmation_sentinel('{"a": 1}', {"pending_plan": {}}) is None


def test_text_summary_drops_internal_noise():
    status = {"task_1": {"model": "qwen3", "location": "http://ollama:11434"}}
    text = format_plan_summary(PACMAN, status)
    assert "PLANNER_COT_INSTRUCTIONS" not in text
    assert "Methodology" not in text
    assert "ollama:11434" not in text
    assert "No agent assigned" not in text
    assert "A new agent will be created" in text
