"""
Builder Agent — creates and deploys ephemeral AI agents on demand.

Receives builder_spec from the Planner (via Orchestrator) and:
1. Resolves tools from the semantic layer
2. Creates ephemeral agent with system_prompt + tools
3. Deploys as Docker container
4. Returns agent card for the Orchestrator to execute against
5. Cleans up after task completion

The build pipeline is registered as @agent.task() decorators in main.py
and injected as self.tool_graph by AbiCore.
"""

from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_core.common.semantic_tools import tool_search_tools
from abi_core.agent.agent import AbiAgent

from config import config


class AbiBuilderAgent(AbiAgent):
    """Builder Agent — creates ephemeral agents and tools on demand."""

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[tool_search_tools],
            system_prompt=prompts.BUILDER_COT_INSTRUCTIONS,
            content_types=['text', 'text/plain'],
        )

    # Uses inherited stream() with heartbeat from AbiAgent.
    # Override when custom build logic is needed.
