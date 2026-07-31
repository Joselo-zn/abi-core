"""
Add commands for ABI Core CLI

Split from a single 2500+ line add.py into one module per domain:
agent.py, service.py, chainlit.py, agent_card.py, policies.py, abi_swarm.py,
plus shared.py/compose.py for cross-domain helpers. This file assembles the
`add` click group from those sub-modules.
"""

import click

from .agent import add_agent
from .service import add_service, add_semantic_layer
from .chainlit import add_chainlit
from .agent_card import add_agent_card
from .policies import add_policies
from .abi_swarm import add_abi_swarm, _update_compose_with_orchestration
from .shared import _generate_agent_card


@click.group()
def add():
    """Add components to existing ABI project"""
    pass


add.add_command(add_agent)
add.add_command(add_service)
add.add_command(add_semantic_layer)
add.add_command(add_chainlit)
add.add_command(add_agent_card)
add.add_command(add_policies)
add.add_command(add_abi_swarm)

# Re-exported so create.py's `from .add import _generate_agent_card` and
# `from .add import _update_compose_with_orchestration` keep working unchanged.
__all__ = ['add', '_generate_agent_card', '_update_compose_with_orchestration']
