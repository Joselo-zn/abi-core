"""Zombie Agent — AbiCore instance."""

import time

from abi_core.agent import AbiCore
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent.config.config import config

# ── Idle mode ──────────────────────────────────────────────────

if config.ZOMBIE_MODE == "idle":
    abi_logging(f"[🧟] Zombie '{config.AGENT_NAME}' in IDLE mode")
    while True:
        time.sleep(60)

# ── Active mode ────────────────────────────────────────────────

abi_logging(f"[🧟→🤖] Zombie activating as '{config.AGENT_NAME}'")
abi_logging(f"[🔧] Tools: {config.TOOL_NAMES}")
abi_logging(f"[🔌] Port: {config.AGENT_PORT}")

agent = AbiCore(config=config, agent_card=config.build_agent_card())
