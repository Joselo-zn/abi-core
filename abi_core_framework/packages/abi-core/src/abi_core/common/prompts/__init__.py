"""
Every static text the system sends to a model, in one place.

One module per agent — each is exactly what that agent sends:

    orchestrator   role prompt, routing decision, synthesis, plan confirmation
    planner        role prompt, technical design, planning, direct_tool content
    builder        role prompt (not reaching a model yet: the Builder runs its DAG)
    guardian       role prompt
    code_agent     ephemeral code agent: TDD instruction, execution prompt,
                   system prompt sections, answer to the reviewer
    reviewer       ephemeral reviewer: role, questions call, one-call repair
    framework      generated agents' role prompt, tool enforcement, LLM turn after a DAG

Everything is re-exported here, lazily (PEP 562), so the import paths that
existed before keep working: ``from abi_core.common.prompts import PLANNER_COT_INSTRUCTIONS``
and ``from abi_core.common import prompts; prompts.GUARDIAL_COT_INSTRUCTIONS``.
The old locations (abi_agents' orchestrator/planner ``prompts.py``,
``ephemeral_prompts``, ``integration_repair``, ``tool_enforcement``,
``routing_tools``) re-export from here too. ``code_tdd`` and ``context_loader``
no longer do: they are community modules and import no agent prompt
(community-imports-product, 2026-10-24).

Lazy on purpose: importing ``abi_core.common.prompts.framework`` (what the
framework uses) must not load the agents' prompt modules. A name is resolved
from its module only when it is first accessed.

Prompt text that lives with its type (user decision 2026-10-10), not here:
- the field descriptions of the structured-output schemas:
  ``abi_core.common.plan_models`` and ``abi_core.agent.routing_tools``;
- the docstrings of the LangChain tools the agents see (library, memory and
  semantic-layer tools): LangChain sends them as the tool's description.

Spec: .abi/specs/implemented/prompts-single-location.md
"""

import importlib

# name -> module in this package that defines it
_EXPORTS = {
    "ORCHESTRATOR_TOT_INSTRUCTIONS": "orchestrator",
    "ROUTING_DECISION_SYSTEM_MESSAGE": "orchestrator",
    "build_methodology_note": "orchestrator",
    "build_routing_decision_prompt": "orchestrator",
    "build_routing_decision_system_message": "orchestrator",
    "build_synthesis_prompt": "orchestrator",
    "build_synthesis_summary_prompt": "orchestrator",
    "format_system_state": "orchestrator",
    "PLANNER_COT_INSTRUCTIONS": "planner",
    "TECHNICAL_DESIGN_INSTRUCTIONS": "planner",
    "build_direct_tool_content_prompt": "planner",
    "build_planning_query": "planner",
    "build_technical_design_query": "planner",
    "BUILDER_COT_INSTRUCTIONS": "builder",
    "GUARDIAL_COT_INSTRUCTIONS": "guardian",
    "ANSWER_PROMPT": "code_agent",
    "CODE_AGENT_ROLE": "code_agent",
    "CODE_AGENT_TASK": "code_agent",
    "TDD_MARKER": "code_agent",
    "TDD_PROMPT_INSTRUCTION": "code_agent",
    "build_code_agent_system_prompt": "code_agent",
    "build_dependency_section": "code_agent",
    "build_execution_prompt": "code_agent",
    "tdd_summary": "code_agent",
    "REVIEWER_QUESTIONS": "reviewer",
    "REVIEWER_ROLE": "reviewer",
    "build_repair_prompt": "reviewer",
    "build_reviewer_questions_prompt": "reviewer",
    "files_with_specs_text": "reviewer",
    "plan_and_design_text": "reviewer",
    "spec_text": "reviewer",
    "specs_text": "reviewer",
    "ENFORCEMENT_RETRY_SYSTEM_PROMPT": "framework",
    "WORKER_PROMPT": "framework",
    "build_enforcement_retry_prompt": "framework",
    "build_pipeline_result_query": "framework",
    "get_enforcement_system_prompt": "framework",
    "build_methodology_selection_prompt": "framework",
    "build_plan_confirmation_interpretation_prompt": "framework",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
