#!/usr/bin/env python3
"""
Orchestrator Agent Main Entry Point
"""

import threading
import uvicorn

from orchestrator import AbiOrchestratorAgent
from web_interface import OrchestratorWebinterface
from abi_core.common.a2a_server import start_server
from abi_core.common.utils import abi_logging

# Import configuration and agent card
from config import config, AGENT_CARD

def orchestrator_factory() -> AbiOrchestratorAgent:
    """
    Factory function to create Orchestrator instance
    
    Returns:
        AbiOrchestratorAgent: Configured agent instance
    """
    try:
        abi_logging(f'[✅] Agent card loaded: {AGENT_CARD.name}')
        abi_logging(f'[📋] Description: {AGENT_CARD.description}')
        
        # Create and return new agent instance
        agent_instance = AbiOrchestratorAgent()
        abi_logging(f'[🚀] Orchestrator agent initialized successfully')
        
        # Start web interface in separate thread
        def start_web_server_interface():
            web_interface = OrchestratorWebinterface(agent_instance)
            abi_logging(f'[🌐] Starting Orchestrator Web Server at 0.0.0.0:{config.WEB_INTERFACE_PORT}')
            uvicorn.run(
                web_interface.app, 
                host="0.0.0.0", 
                port=config.WEB_INTERFACE_PORT,
                log_level="info"
            )

        web_thread = threading.Thread(target=start_web_server_interface, daemon=True)
        web_thread.start()
        abi_logging(f'[✅] Orchestrator web interface started on port {config.WEB_INTERFACE_PORT}')
        
        return agent_instance
        
    except Exception as e:
        abi_logging(f'[❌] Error creating Orchestrator agent: {e}')
        raise


def main():
    """Main entry point for Orchestrator agent"""
    
    abi_logging(f'[🌟] Starting {config.AGENT_DISPLAY_NAME} Server')
    abi_logging(f'[🌐] Host: 0.0.0.0')
    abi_logging(f'[🔌] Port: {config.AGENT_PORT}')
    abi_logging(f'[�] Web tInterface Port: {config.WEB_INTERFACE_PORT}')
    abi_logging(f'[📄] Agent Card: {config.AGENT_CARD}')
    abi_logging(f'[🤖] Model: {config.MODEL_NAME}')
    abi_logging(f'[🔗] Ollama: {config.OLLAMA_HOST}')
    
    try:
        # Create agent
        agent = orchestrator_factory()
        
        # Start the A2A server with the agent card
        start_server(
            host='0.0.0.0',
            port=config.AGENT_PORT,
            agent_card=AGENT_CARD,
            agent=agent
        )
        
    except KeyboardInterrupt:
        abi_logging('[🛑] Orchestrator agent stopped by user')
        return 0
    except Exception as e:
        abi_logging(f'[�] Fcatal error starting Orchestrator agent: {e}')
        return 1


if __name__ == '__main__':
    exit(main())
