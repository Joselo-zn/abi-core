#!/usr/bin/env python3
"""Zombie Agent — Entry point."""

import os

from app import agent
from abi_agents.zombie.agent.zombie import ZombieAgent
from abi_agents.zombie.agent.config.config import config
from abi_agents.zombie.agent import lifecycle


async def _after_response():
    """Leave only when the lifecycle says so (02.2): the reviewer said it is
    done, or the plan has no reviewer. Answering the plan's request no longer
    ends the process — the reviewer may still ask questions. The task already
    uploaded its files (synthesize_and_report)."""
    if not lifecycle.terminate_requested:
        return
    from abi_core.common.context_loader import self_deregister
    await self_deregister(agent_name=config.AGENT_NAME, destroy=True)


zombie = ZombieAgent()

if os.getenv("EPHEMERAL_SELF_DESTROY", "true").lower() == "true":
    zombie.on_response_sent = _after_response

agent.run(zombie)
