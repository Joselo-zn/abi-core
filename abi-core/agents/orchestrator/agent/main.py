import os
import logging
import json

from pathlib import Path

from a2a.types import AgentCard
from agent.orchestrator import OrchestratorAgent
from common.a2a_client import start_client

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

def orchestrator_factory(agent_card_dir: AgentCard):
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    if agent_card.name != "Orchestrator Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected Agentagent_card name: {agent_card.name!r}")
    return OrchestratorAgent()


if __name__ == "__main__":
    
    start_client("0.0.0.0", 8002, agent_card_dir, orchestrator_factory)
