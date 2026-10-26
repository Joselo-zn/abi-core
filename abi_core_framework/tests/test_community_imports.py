"""Community modules never load product modules.

User rule (2026-10-17): the framework (community) must run without the
product. Each community module is imported in a clean interpreter and the
modules it loaded are checked against the product list: the agents' prompt
modules and the agent-level code that stays on the product side.

Spec: .abi/specs/not-implemented/community-imports-product.md
"""

import json
import subprocess
import sys

import pytest

PRODUCT_MODULES = {
    "abi_core.common.prompts.orchestrator",
    "abi_core.common.prompts.planner",
    "abi_core.common.prompts.builder",
    "abi_core.common.prompts.guardian",
    "abi_core.common.prompts.code_agent",
    "abi_core.common.prompts.reviewer",
    "abi_core.common.ephemeral_prompts",
    "abi_core.common.integration_repair",
    "abi_core.agent.routing_tools",
}

COMMUNITY_MODULES = [
    "abi_core.agent.agent",
    "abi_core.agent.plan_confirmation",
    "abi_core.agent.llm_provider",
    "abi_core.common.prompts",
    "abi_core.common.prompts.framework",
    "abi_core.common.context_loader",
    "abi_core.common.code_tdd",
    "abi_core.common.integration_review",
    "abi_core.common.methodology_tools",
    "abi_core.common.tool_enforcement",
    "abi_core.common.semantic_tools",
    "abi_core.common.agent_card_loader",
    "abi_core.common.plan_models",
    "abi_core.common.sandbox",
]

_PROBE = """
import importlib, json, sys
importlib.import_module(sys.argv[1])
print(json.dumps(sorted(m for m in sys.modules if m.startswith(("abi_core", "abi_agents")))))
"""


def _loaded_by(module: str) -> set:
    out = subprocess.run([sys.executable, "-c", _PROBE, module],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return set(json.loads(out.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("module", COMMUNITY_MODULES)
def test_community_module_loads_no_product_module(module):
    loaded = _loaded_by(module)
    leaked = sorted(m for m in loaded if m in PRODUCT_MODULES or m.startswith("abi_agents"))
    assert not leaked, f"{module} loads product modules: {leaked}"


def test_lazy_prompts_package_still_exposes_agent_prompts():
    """Backward compatibility: templates and examples read
    prompts.GUARDIAL_COT_INSTRUCTIONS / prompts.WORKER_PROMPT."""
    from abi_core.common import prompts
    from abi_core.common.prompts.guardian import GUARDIAL_COT_INSTRUCTIONS
    from abi_core.common.prompts.framework import WORKER_PROMPT

    assert prompts.GUARDIAL_COT_INSTRUCTIONS == GUARDIAL_COT_INSTRUCTIONS
    assert prompts.WORKER_PROMPT == WORKER_PROMPT
    assert "PLANNER_COT_INSTRUCTIONS" in dir(prompts)
    with pytest.raises(AttributeError):
        prompts.NOT_A_PROMPT
