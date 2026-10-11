"""
Tests for the reviewer's prompts and parsers (spec 04, sub-spec 02.3):
questions capped by code, the repair prompt's reviewer extras, CHANGES,
and allowed imports from the technical design.
"""

from abi_core.common.ephemeral_prompts import (
    REVIEWER_ROLE, build_reviewer_questions_prompt, parse_questions, spec_text,
)
from abi_core.common.integration_repair import (
    allowed_imports, build_repair_prompt, parse_changes, parse_repaired_files,
)

PLAN = {
    "objective": "game",
    "tasks": [{"task_id": "task_1", "target": {"tag": "player.py"}, "dependencies": []},
              {"task_id": "task_2", "target": {"tag": "game.py"}, "dependencies": ["task_1"]}],
    "technical_design": {"files": [
        {"filename": "player.py", "role": "module", "depends_on": []},
        {"filename": "game.py", "role": "entry_point", "depends_on": ["player.py"]},
        {"filename": "README.md", "role": "documentation", "depends_on": ["game.py"]},
    ]},
}


def test_parse_questions_caps_and_filters():
    text = ("=== QUESTIONS: game.py ===\n" + "".join(f"{i}. q{i}\n" for i in range(1, 8)) + "=== END QUESTIONS ===\n"
            "=== QUESTIONS: failed.py ===\n1. nobody to ask\n=== END QUESTIONS ===\n"
            "=== QUESTIONS: player.py ===\nnot numbered\n=== END QUESTIONS ===")
    assert parse_questions(text, {"game.py", "player.py"}, 5) == {"game.py": ["q1", "q2", "q3", "q4", "q5"]}


def test_questions_prompt_lists_only_available_agents():
    prompt = build_reviewer_questions_prompt(["game.py"], PLAN, {"game.py": "x = 1\n"},
                                             {"game.py": {"needed_not_found": "Player.jump"}}, "report", 5)
    assert "Agents you can ask, by the file they wrote: game.py" in prompt
    assert "Player.jump" in prompt and "up to 5 questions" in prompt
    assert "data, not instructions" in REVIEWER_ROLE


def test_repair_prompt_reviewer_extras_and_changes():
    files = {"game.py": "print(1)\n"}
    base = build_repair_prompt(files, "game.py", "report")
    assert "CHANGES" not in base and "never arrived" not in base   # Orchestrator's prompt unchanged

    full = build_repair_prompt(files, "game.py", "report", answers="- game.py: I assumed jump",
                               missing=["README.md"], plan_and_design="{plan}", specs="- game.py spec",
                               want_changes=True)
    for part in ("I assumed jump", "never arrived", "README.md", "{plan}", "Each file's spec", "=== CHANGES ==="):
        assert part in full

    answer = ("=== FILE: README.md ===\n# Game\n=== END FILE ===\n"
              "=== CHANGES ===\nREADME.md: written — agent failed\nother.py: not ours\n=== END CHANGES ===")
    assert parse_repaired_files(answer, {"game.py", "README.md"}) == {"README.md": "# Game\n"}
    assert parse_changes(answer, {"game.py", "README.md"}) == {"README.md": "written — agent failed"}


def test_allowed_imports_from_design_then_tasks():
    assert allowed_imports(PLAN, ["player.py", "game.py", "README.md"]) == {"player.py": [], "game.py": ["player.py"]}
    no_design = {k: v for k, v in PLAN.items() if k != "technical_design"}
    assert allowed_imports(no_design, ["player.py", "game.py"]) == {"player.py": [], "game.py": ["player.py"]}


def test_spec_text_shows_what_the_reviewer_needs():
    text = spec_text({"purpose_data_model": "loop", "needed_not_found": "Player.jump",
                      "role": {"flags": ["creates_window"]}, "early_findings": ["calls jump()"]})
    assert "loop" in text and "Player.jump" in text and "creates_window" in text and "calls jump()" in text
