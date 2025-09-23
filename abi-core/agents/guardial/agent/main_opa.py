import os
import logging
import json

from pathlib import Path
from a2a.types import AgentCard
from agent.guardial_opa import AbiGuardialOPA
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

def guardian_factory(agent_card_dir: AgentCard):
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    if agent_card.name != "Abi Guardial Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected Agent card name: {agent_card.name!r}")
    return AbiGuardialOPA()

if __name__ == '__main__':
    start_server("0.0.0.0", 8003, agent_card_dir, guardian_factory)