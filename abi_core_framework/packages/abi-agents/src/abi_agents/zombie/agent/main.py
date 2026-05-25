#!/usr/bin/env python3
"""Zombie Agent — Entry point."""

import os

from app import agent
from abi_agents.zombie.agent.zombie import ZombieAgent
from abi_agents.zombie.agent.config.config import config
from abi_core.common.utils import abi_logging


async def _post_response_cleanup():
    """Cleanup after A2A response is sent: upload artifacts, deregister + exit."""
    from abi_core.common.artifact_store import upload_workspace_artifacts
    from abi_core.common.context_loader import self_deregister

    # Upload generated files from workspace to MinIO
    try:
        uploaded = await upload_workspace_artifacts(
            agent_name=config.AGENT_NAME,
            workspace="/app/workspace",
        )
        if uploaded:
            abi_logging(f"[📤] Uploaded {len(uploaded)} artifact(s) to MinIO")
    except Exception as e:
        abi_logging(f"[⚠️] Artifact upload failed: {e}")

    await self_deregister(agent_name=config.AGENT_NAME, destroy=True)


zombie = ZombieAgent()

if os.getenv("EPHEMERAL_SELF_DESTROY", "true").lower() == "true":
    zombie.on_response_sent = _post_response_cleanup

agent.run(zombie)
