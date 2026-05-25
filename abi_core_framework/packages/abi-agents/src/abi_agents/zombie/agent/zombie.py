"""Zombie Agent — Self-configuring ephemeral agent class."""

from abi_core.agent.agent import AbiAgent
from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent.config.config import config

# Tools loaded once at init, shared with DAG functions in main.py
ZOMBIE_TOOLS = []


class ZombieAgent(AbiAgent):
    """Self-configuring ephemeral agent.

    Reads all configuration from environment variables via config.py.
    Tools are loaded at init and shared with the DAG phases.
    """

    def __init__(self):
        from abi_core.common.context_loader import load_agent_context_sync

        ctx = load_agent_context_sync(
            mcp_tool_names=config.TOOL_NAMES if config.TOOL_NAMES else None,
            library_tool_names=config.LIBRARY_TOOL_NAMES if config.LIBRARY_TOOL_NAMES else None,
            workspace=config.WORKSPACE,
        )

        ZOMBIE_TOOLS.clear()
        ZOMBIE_TOOLS.extend(ctx["lib_tools"] + ctx["mcp_tools"])

        full_prompt = prompts.ZOMBIE_AGENT_PROMPT.format(
            system_prompt=config.SYSTEM_PROMPT
        )

        tool_list = [tool.name for tool in ZOMBIE_TOOLS]
        abi_logging(f"[🤖] My task: {config.SYSTEM_PROMPT}")
        abi_logging(f"[🔧] My tools to complete the task: {len(ZOMBIE_TOOLS)} tools: {tool_list}")

        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=ZOMBIE_TOOLS,
            system_prompt=full_prompt,
        )
