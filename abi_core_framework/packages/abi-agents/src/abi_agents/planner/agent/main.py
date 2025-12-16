#!/usr/bin/env python3
"""
Planner Agent Main Entry Point
"""

from planner import AbiPlannerAgent
from abi_core.common.a2a_server import start_server
from abi_core.common.utils import abi_logging

# Import configuration and agent card
from config import config, AGENT_CARD


def planner_factory() -> AbiPlannerAgent:
    """
    Factory function to create Planner instance
    
    Returns:
        AbiPlannerAgent: Configured agent instance
    """
    try:
        abi_logging(f'[✅] Agent card loaded: {AGENT_CARD.name}')
        abi_logging(f'[📋] Description: {AGENT_CARD.description}')
        
        # Create and return new agent instance
        agent_instance = AbiPlannerAgent()
        abi_logging(f'[🚀] Planner agent initialized successfully')
        
        return agent_instance
        
    except Exception as e:
        abi_logging(f'[❌] Error creating Planner agent: {e}')
        raise


def main():
    """Main entry point for Planner agent"""
    
    abi_logging(f'[🌟] Starting {config.AGENT_DISPLAY_NAME} Server')
    abi_logging(f'[🌐] Host: 0.0.0.0')
    abi_logging(f'[🔌] Port: {config.AGENT_PORT}')
    abi_logging(f'[📄] Agent Card: {config.AGENT_CARD}')
    abi_logging(f'[🤖] Model: {config.MODEL_NAME}')
    abi_logging(f'[🔗] Ollama: {config.OLLAMA_HOST}')
    
    try:
        # Create agent
        agent = planner_factory()
        
        # Start the A2A server with the agent card
        start_server(
            host='0.0.0.0',
            port=config.AGENT_PORT,
            agent_card=AGENT_CARD,
            agent=agent
        )
        
    except KeyboardInterrupt:
        abi_logging('[🛑] Planner agent stopped by user')
        return 0
    except Exception as e:
        abi_logging(f'[💥] Fatal error starting Planner agent: {e}')
        return 1


if __name__ == '__main__':
    exit(main())
