import os
import logging
import json
import asyncio
import threading

from pathlib import Path

from a2a.types import AgentCard
from agent.observer import AbiObserverAgent
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

# Global observer instance for API access
observer_instance = None

def observer_factory(agent_card_dir: AgentCard):
    """Factory function for creating Observer agent"""
    global observer_instance
    
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    
    if agent_card.name != "Abi Observer Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected Agent card name: {agent_card.name!r}")
    
    observer_instance = AbiObserverAgent()
    
    # Start API server in background thread
    def start_api():
        asyncio.run(observer_instance.start_api_server(port=8080))
    
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    logger.info("🌐 Observer API started on port 8080")
    logger.info("📊 Grafana Dashboard available at http://localhost:3000")
    logger.info("📈 Prometheus available at http://localhost:9090")
    
    return observer_instance


if __name__ == "__main__":
    logger.info("🚀 Starting ABI Observer Agent...")
    start_server("0.0.0.0", 8004, agent_card_dir, observer_factory)