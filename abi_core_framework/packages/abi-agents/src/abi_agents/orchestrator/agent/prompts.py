"""
Orchestrator prompts — they live in abi_core.common.prompts.orchestrator,
with every other prompt. Re-exported here: config.py exposes them as
``config.*``. Spec: .abi/specs/implemented/prompts-single-location.md
"""

from abi_core.common.prompts.orchestrator import (  # noqa: F401  (re-exported)
    ROUTING_DECISION_SYSTEM_MESSAGE,
    build_routing_decision_prompt,
    build_routing_decision_system_message,
    build_synthesis_prompt,
    build_synthesis_summary_prompt,
)
