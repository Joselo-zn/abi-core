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

Everything is re-exported here, so the import paths that existed before
keep working: ``from abi_core.common.prompts import PLANNER_COT_INSTRUCTIONS``
and ``from abi_core.common import prompts; prompts.GUARDIAL_COT_INSTRUCTIONS``.
The old locations (abi_agents' orchestrator/planner ``prompts.py``,
``ephemeral_prompts``, ``code_tdd``, ``context_loader``, ``integration_repair``,
``tool_enforcement``, ``routing_tools``) re-export from here too.

Prompt text that lives with its type (user decision 2026-10-10), not here:
- the field descriptions of the structured-output schemas:
  ``abi_core.common.plan_models`` and ``abi_core.agent.routing_tools``;
- the docstrings of the LangChain tools the agents see (library, memory and
  semantic-layer tools): LangChain sends them as the tool's description.

Spec: .abi/specs/implemented/prompts-single-location.md
"""

from abi_core.common.prompts.orchestrator import (
    ORCHESTRATOR_TOT_INSTRUCTIONS,
    ROUTING_DECISION_SYSTEM_MESSAGE,
    build_methodology_note,
    build_plan_confirmation_interpretation_prompt,
    build_routing_decision_prompt,
    build_routing_decision_system_message,
    build_synthesis_prompt,
    format_system_state,
)
from abi_core.common.prompts.planner import (
    PLANNER_COT_INSTRUCTIONS,
    TECHNICAL_DESIGN_INSTRUCTIONS,
    build_direct_tool_content_prompt,
    build_methodology_selection_prompt,
    build_planning_query,
    build_technical_design_query,
)
from abi_core.common.prompts.builder import BUILDER_COT_INSTRUCTIONS
from abi_core.common.prompts.guardian import GUARDIAL_COT_INSTRUCTIONS
from abi_core.common.prompts.code_agent import (
    ANSWER_PROMPT,
    CODE_AGENT_ROLE,
    CODE_AGENT_TASK,
    TDD_MARKER,
    TDD_PROMPT_INSTRUCTION,
    build_code_agent_system_prompt,
    build_dependency_section,
    build_execution_prompt,
    tdd_summary,
)
from abi_core.common.prompts.reviewer import (
    REVIEWER_QUESTIONS,
    REVIEWER_ROLE,
    build_repair_prompt,
    build_reviewer_questions_prompt,
    files_with_specs_text,
    plan_and_design_text,
    spec_text,
    specs_text,
)
from abi_core.common.prompts.framework import (
    ENFORCEMENT_RETRY_SYSTEM_PROMPT,
    WORKER_PROMPT,
    build_enforcement_retry_prompt,
    build_pipeline_result_query,
    get_enforcement_system_prompt,
)
