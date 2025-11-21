import os
import logging
import json

from pathlib import Path

from a2a.types import AgentCard
from agent.planner import AbiPlannerAgent
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

def planner_factory(agent_card_dir: AgentCard):
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    if agent_card.name.strip() != "Abi Planner Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected agent_card name: {agent_card.name!r}")
    return AbiPlannerAgent()


if __name__ == "__main__":
    
    logger.info(f"Starting planner with agent_card_dir: {agent_card_dir}")
    
    # Create the agent instance using the factory
    try:
        agent_instance = planner_factory(agent_card_dir)
        logger.info(f"Created agent instance: {type(agent_instance)} - {agent_instance}")
        logger.info(f"Agent has agent_name: {hasattr(agent_instance, 'agent_name')}")
        if hasattr(agent_instance, 'agent_name'):
            logger.info(f"Agent name: {agent_instance.agent_name}")
    except Exception as e:
        logger.error(f"Failed to create agent instance: {e}")
        raise
    
    start_server("0.0.0.0", 11437, agent_card_dir, agent_instance)
