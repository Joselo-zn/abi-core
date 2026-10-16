"""Every prompt in one place (abi_core.common.prompts), text unchanged.

render_all() renders every static prompt text that reaches a model, with
fixed inputs, through the import paths that existed BEFORE the prompts
moved (so it also checks backward compatibility). The snapshot in
fixtures/prompts_snapshot.json was written with the code before the move;
after it, every text must be byte-identical.

Regenerate (only when a prompt is changed on purpose):
    python tests/test_prompts_location.py --write

Spec: .abi/specs/implemented/prompts-single-location.md
"""

import asyncio
import importlib
import json
import os
import sys
import types
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "fixtures" / "prompts_snapshot.json"

_PLAN = {
    "objective": "A small game",
    "tasks": [
        {"task_id": "task_1", "description": "Write a Python file named player.py",
         "target": {"tag": "player.py"}, "dependencies": []},
        {"task_id": "task_2", "description": "Write a Python file named main.py",
         "target": {"tag": "main.py"}, "dependencies": ["task_1"]},
    ],
    "technical_design": {"files": [
        {"filename": "player.py", "role": "module", "depends_on": []},
        {"filename": "main.py", "role": "entry_point", "depends_on": ["player.py"]},
    ]},
}
# The plan a code agent reads from its project folder: with responsibilities.
_PLAN_IN_FOLDER = {**_PLAN, "technical_design": {"files": [
    {"filename": "player.py", "role": "module", "responsibility": "the player", "depends_on": []},
    {"filename": "main.py", "role": "entry_point", "responsibility": "runs the game",
     "depends_on": ["player.py"]},
]}}
_FILES = {"player.py": "class Player:\n    pass\n", "main.py": "from player import Player\n"}
_TDD = {"purpose_data_model": "the player", "needed_not_found": "none",
        "exposes": {"classes": [{"name": "Player", "methods": []}]},
        "assumes": {"main.py": ["Player"]}, "role": {"flags": ["has_main_guard"]},
        "resources": ["a.png"], "early_findings": ["x"]}


class _Tool:
    def __init__(self, name, description):
        self.name, self.description = name, description


def _lc_tools():
    from langchain_core.tools import tool

    @tool
    def write_file(path: str) -> str:
        """Write a file"""
        return path

    @tool
    def run_shell(cmd: str) -> str:
        """Run a command"""
        return cmd

    return [write_file, run_shell]


def _zombie_steps():
    """The zombie's steps.py with a stand-in `app` (identity decorators)."""
    class _Agent:
        def step(self, *a, **k):
            return lambda fn: fn
    sys.modules["app"] = types.SimpleNamespace(agent=_Agent())
    try:
        return importlib.import_module("abi_agents.zombie.agent.steps")
    finally:
        sys.modules.pop("app", None)


async def _code_agent_system_prompts(steps):
    """The system prompt and query analyze_and_execute sends, captured at
    invoke(), for a context with and without memory/plan/contracts."""
    import abi_core.agent.llm_provider as llm_provider
    import abi_core.memory as memory
    from abi_core.common import project_store

    captured = []

    async def fake_load_json(run_id, area, filename, store=None):
        assert (run_id, area, filename) == ("r1", "plan", "plan.json")
        return _PLAN_IN_FOLDER

    async def fake_invoke(llm_config, prompt, **kwargs):
        captured.append({"query": prompt, "system": kwargs.get("system_prompt")})
        raise RuntimeError("captured")

    async def fake_recall(**kwargs):
        return "earlier: the user likes blue"

    old = (llm_provider.invoke, memory.recall_memory_context, project_store.load_json,
           steps.config.AGENT_MEMORY_URL, steps.config.CONTEXT_ID, steps.config.SYSTEM_PROMPT)
    llm_provider.invoke, memory.recall_memory_context = fake_invoke, fake_recall
    project_store.load_json = fake_load_json
    steps.config.SYSTEM_PROMPT = "Write a Python file named main.py"
    steps.ZOMBIE_TOOLS[:] = [_Tool("write_file", "Write a file"), _Tool("run_shell", "Run a command")]
    full = {
        "artifacts": ["/app/workspace/player.py"],
        "process_context": {"run_id": "r1", "objective": "A small game", "total_tasks": 2,
                            "tasks": _PLAN["tasks"]},
        "dependency_contracts": {"task_1": {"files": {"player.py": {
            "classes": [{"name": "Player", "methods": ["__init__(self)", "move(self, dx)"]}],
            "functions": [{"name": "make", "signature": "make()"}]}}}},
        "dependency_tdds": {"player.py": _TDD},
    }
    try:
        steps.config.AGENT_MEMORY_URL, steps.config.CONTEXT_ID = "http://ams", "task_2"
        try:
            await steps.analyze_and_execute(full, "Write main.py")
        except Exception:
            pass
        steps.config.AGENT_MEMORY_URL, steps.config.CONTEXT_ID = "", ""
        try:
            await steps.analyze_and_execute({}, "Write main.py")
        except Exception:
            pass
    finally:
        (llm_provider.invoke, memory.recall_memory_context, project_store.load_json,
         steps.config.AGENT_MEMORY_URL, steps.config.CONTEXT_ID, steps.config.SYSTEM_PROMPT) = old
    return captured


async def _answer_prompt(steps):
    import abi_core.agent.llm_provider as llm_provider
    captured = []

    async def fake_invoke(llm_config, prompt, **kwargs):
        captured.append(prompt)
        return "1. because"

    old = llm_provider.invoke
    llm_provider.invoke = fake_invoke
    steps.lifecycle.work_record.clear()
    steps.lifecycle.work_record.update({"task": "Write main.py", "files_written": ["main.py"],
                                        "spec": {"purpose_data_model": "x"}})
    steps.lifecycle.questions_answered = 0
    old_transcript = steps.lifecycle.generation_transcript
    steps.lifecycle.generation_transcript = lambda *a, **k: "[user] write main.py"
    try:
        await steps.answer_questions(["Why?", "What owns the score?"])
    finally:
        llm_provider.invoke = old
        steps.lifecycle.generation_transcript = old_transcript
    return captured[0]


def render_all() -> dict:
    os.environ.setdefault("AGENT_NAME", "z")
    from abi_core.common import prompts
    from abi_core.common.prompts import (
        ORCHESTRATOR_TOT_INSTRUCTIONS, PLANNER_COT_INSTRUCTIONS, TECHNICAL_DESIGN_INSTRUCTIONS,
        BUILDER_COT_INSTRUCTIONS, WORKER_PROMPT, build_methodology_selection_prompt,
        build_plan_confirmation_interpretation_prompt,
    )
    from abi_agents.orchestrator.agent import prompts as orch
    from abi_agents.planner.agent import prompts as plan
    from abi_core.agent.routing_tools import format_system_state
    from abi_core.common.code_tdd import TDD_PROMPT_INSTRUCTION, TDD_MARKER, tdd_summary
    from abi_core.common.context_loader import build_execution_prompt
    from abi_core.common.ephemeral_prompts import (
        REVIEWER_ROLE, REVIEWER_QUESTIONS, build_reviewer_questions_prompt, spec_text,
        specs_text, files_with_specs_text, plan_and_design_text,
    )
    from abi_core.common.integration_repair import build_repair_prompt
    from abi_core.common.tool_enforcement import ToolTracker, get_enforcement_system_prompt

    out = {
        "ORCHESTRATOR_TOT_INSTRUCTIONS": ORCHESTRATOR_TOT_INSTRUCTIONS,
        "GUARDIAL_COT_INSTRUCTIONS": prompts.GUARDIAL_COT_INSTRUCTIONS,
        "PLANNER_COT_INSTRUCTIONS": PLANNER_COT_INSTRUCTIONS,
        "TECHNICAL_DESIGN_INSTRUCTIONS": TECHNICAL_DESIGN_INSTRUCTIONS,
        "BUILDER_COT_INSTRUCTIONS": BUILDER_COT_INSTRUCTIONS,
        "WORKER_PROMPT": WORKER_PROMPT,
        "methodology_selection": build_methodology_selection_prompt("build a game"),
        "plan_confirmation": build_plan_confirmation_interpretation_prompt("Plan: 2 tasks", "yes go"),
        "ROUTING_DECISION_SYSTEM_MESSAGE": orch.ROUTING_DECISION_SYSTEM_MESSAGE,
        "routing_system_message": orch.build_routing_decision_system_message(),
        "routing_prompt": orch.build_routing_decision_prompt("[SYSTEM STATE] x", "hola"),
        "routing_prompt_gathered": orch.build_routing_decision_prompt("", "hola", "found 2 agents"),
        "synthesis": orch.build_synthesis_prompt(_PLAN, 2, ["main.py: http://x"]),
        "synthesis_report": orch.build_synthesis_prompt(_PLAN, 2, [], "1 error"),
        "synthesis_summary": orch.build_synthesis_summary_prompt(
            "quiero un juego pequeño", "A small game",
            [{"title": "Jugador", "deliverable": {"tag": "player.py"}}, {"title": "Main loop", "deliverable": None}]),
        "system_state_all": format_system_state("plan", "question?", "user: hi"),
        "system_state_none": format_system_state(None, None),
        # Inline f-string in orchestrator/agent/steps.py (build_workflow),
        # copied verbatim from the code before the move.
        "methodology_note": (lambda methodology, rationale: f"[Metodología del plan: {methodology}] {rationale}\n\n")(
            "Agile (Scrum/Kanban)", "fixed framing"),
        "technical_design_query": plan.build_technical_design_query("make pong", {"a": 1}),
        "planning_query": plan.build_planning_query("make pong", {"a": 1}),
        "planning_query_design": plan.build_planning_query("make pong", {"a": 1}, {"files": []}),
        "direct_tool_content": plan.build_direct_tool_content_prompt("An itinerary"),
        "TDD_PROMPT_INSTRUCTION": TDD_PROMPT_INSTRUCTION,
        "TDD_MARKER": TDD_MARKER,
        "tdd_summary": tdd_summary(_TDD),
        "execution_prompt": build_execution_prompt(
            "Write main.py", [_Tool("write_file", "Write a file")], ["/app/workspace/player.py"]),
        "execution_prompt_bare": build_execution_prompt("Write main.py"),
        "REVIEWER_ROLE": REVIEWER_ROLE,
        "REVIEWER_QUESTIONS": REVIEWER_QUESTIONS,
        "reviewer_questions": build_reviewer_questions_prompt(
            ["main.py"], _PLAN, _FILES, {"player.py": _TDD}, "2 errors"),
        "spec_text": spec_text(_TDD),
        "specs_text": specs_text({"player.py": _TDD}),
        "files_with_specs_text": files_with_specs_text(_FILES, {"player.py": _TDD}),
        "plan_and_design_text": plan_and_design_text(_PLAN),
        "repair_minimal": build_repair_prompt(_FILES, "main.py", "1 error"),
        "repair_full": build_repair_prompt(
            _FILES, "main.py", "1 error", {"main.py": ["player.py"], "player.py": []},
            answers="main.py: because", missing=["hud.py"], plan_and_design="design",
            specs="specs", want_changes=True),
        "enforcement_system": get_enforcement_system_prompt(["write_file", "run_shell"]),
        "enforcement_retry": ToolTracker(_lc_tools(), ["write_file", "run_shell"],
                                         ).get_enforcement_prompt("I would write the file"),
        # Inline literals in llm_provider.py (enforcement retry) and agent.py
        # (LLM turn after the DAG), copied verbatim from the code before the move.
        "enforcement_retry_system": "You MUST call the required tools. Do not explain. Just call them.",
        "pipeline_result_query": (lambda dag_summary, query: f"[Pipeline result]: {dag_summary}\n\nOriginal request: {query}")(
            '{"ok": true}', "hola"),
    }

    steps = _zombie_steps()
    captured = asyncio.run(_code_agent_system_prompts(steps))
    out["code_agent_system_full"] = captured[0]["system"]
    out["code_agent_query_full"] = captured[0]["query"]
    out["code_agent_system_bare"] = captured[1]["system"]
    out["code_agent_answer_prompt"] = asyncio.run(_answer_prompt(steps))
    return out


def test_every_prompt_text_unchanged():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = render_all()
    assert sorted(current) == sorted(snapshot)
    changed = [k for k in snapshot if current[k] != snapshot[k]]
    assert not changed, f"prompt text changed: {changed}"


if __name__ == "__main__" and "--write" in sys.argv:
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(render_all(), ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {SNAPSHOT}")
