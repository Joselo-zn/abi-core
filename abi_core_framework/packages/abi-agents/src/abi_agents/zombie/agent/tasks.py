"""Zombie Agent — Tasks: the role decides which entry task this zombie has.

    ZOMBIE_ROLE=code (default)   code_agent_tasks — write one file, answer the reviewer (02.2)
    ZOMBIE_ROLE=reviewer         reviewer — review and repair the run's set (02.3)

AbiCore imports this module by name; importing the role's module registers
its task(s) and steps.
"""

from abi_agents.zombie.agent.config.config import config

if config.ZOMBIE_ROLE == "reviewer":
    from abi_agents.zombie.agent import reviewer  # noqa: F401
else:
    from abi_agents.zombie.agent import code_agent_tasks  # noqa: F401
