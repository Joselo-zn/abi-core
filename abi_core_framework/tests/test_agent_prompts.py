"""
The persistent agents' prompts stay consistent with what the code does.
Spec: .abi/specs/not-implemented/persistent-agent-prompts.md
"""

import re

import abi_core.common.prompts as prompts
from abi_core.common.plan_models import PlanTask


def test_planner_prompt_matches_task_schema():
    """The Planner decodes against PlanTask; its prompt must not ask for a
    field the schema doesn't have (it used to require a `steps` array)."""
    text = prompts.PLANNER_COT_INSTRUCTIONS
    assert "steps" not in PlanTask.model_fields
    assert "steps" not in text.lower()  # the old prompt: 'MUST include a "steps" array'
    for field in ("description", "title", "direct_tool"):
        assert field in text
    assert "target.tag" in text
    assert "500 characters" in text  # PlanTask.description max_length
    assert PlanTask.model_fields["description"].metadata  # the cap still exists in the schema


def test_role_prompts_are_plain_strings_without_placeholders():
    for name in ("PLANNER_COT_INSTRUCTIONS", "TECHNICAL_DESIGN_INSTRUCTIONS",
                 "BUILDER_COT_INSTRUCTIONS", "ORCHESTRATOR_TOT_INSTRUCTIONS"):
        text = getattr(prompts, name)
        assert not re.search(r"\{[a-z_]+\}", text), f"{name} has an unformatted placeholder"


def test_dead_prompts_removed_and_scaffold_prompt_kept():
    for name in ("ORCHESTRATOR_QA_COT_PLANNER", "ORCHESTRATOR_PLANNER_SUMMARY", "VERIFIER_COT_INSTRUCTIONS",
                 "OBSERVER_COT_INSTRUCTIONS", "ORCHESTRATOR_TRIAGE_PROMPT"):
        assert not hasattr(prompts, name)
    # Used by `abi-core add agent` (scaffolding/agent/agent.py.j2).
    assert prompts.WORKER_PROMPT


def test_orchestrator_prompt_carries_synthesis_rules():
    text = prompts.ORCHESTRATOR_TOT_INSTRUCTIONS
    # C2: the model describes the deliverable; the verdict, errors and links are added by code.
    assert "# Synthesis" in text
    for rule in ("do not judge", "added below your text by code", "in the language of the user's request"):
        assert rule in text
