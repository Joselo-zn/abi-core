#!/usr/bin/env python3
"""Zombie Agent — Entry point."""

import os

from app import agent
from abi_agents.zombie.agent.zombie import ZombieAgent
from abi_agents.zombie.agent.config.config import config


async def _post_response_cleanup():
    """Cleanup after A2A response is sent: deregister + exit."""
    from abi_core.common.context_loader import self_deregister
    await self_deregister(agent_name=config.AGENT_NAME, destroy=True)


zombie = ZombieAgent()

if os.getenv("EPHEMERAL_SELF_DESTROY", "true").lower() == "true":
    zombie.on_response_sent = _post_response_cleanup

agent.run(zombie)
