import os
import logging
import json

from pathlib import Path

from a2a.types import AgentCard
from agent.orchestrator import AbiOrchestratorAgent
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

def orchestrator_factory(agent_card_dir: AgentCard):
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    if agent_card.name != "Abi Orchestrator Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected Agentagent_card name: {agent_card.name!r}")
    return AbiOrchestratorAgent()


if __name__ == "__main__":
    
    start_server("0.0.0.0", 8002, agent_card_dir, orchestrator_factory)
