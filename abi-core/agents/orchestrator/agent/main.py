import os
import json
import logging
import sys

import httpx
import uvicorn

from a2a.types import AgentCard
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)

from types import json
from pathlib import Path

from common.agent_executor import ABIAgentExecutor
from agent.orchestrator import OrchestratorAgent


logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')


def get_agent(agent_card: AgentCard) -> OrchestratorAgent :
    try:
        if agent_card.name == "Orchestrator Agent":
            return OrchestratorAgent()
    except Exception as e:
        raise e

def main(host: str, port: int, agent_card: json):
    """Starts ABI Orchestator agent server
    Parasm:
        host: Agent host in string format
        port: Agent port in int format
        agent_card: Agent Card in JSON format
    """
    try:
        if not agent_card:
            raise ValueError('[!] Abi Agent card is required')
        
        with Path.open(agent_card) as file:
            data = json.load(file)
        agent_card = AgentCard(**data)

        client = httpx.AsyncClient()
        push_notification_config_store = InMemoryPushNotificationConfigStore()
        push_notification_sender = BasePushNotificationSender(
            client,
            confi_store=push_notification_config_store
        )

        request_handler = DefaultRequestHandler(
            agent_executor=ABIAgentExecutor(agent=get_agent(agent_card)),
            task_store=InMemoryTaskStore(),
            push_config_store=push_notification_config_store,
            push_sender=push_notification_sender
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        logger.info(f'[🚀] Starting ABI server on {host}:{port}')
        uvicorn.run(server.build(), host=host, port=port)

    except FileNotFoundError:
        logger.error(f"Error: File '{agent_card}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error: File '{agent_card}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)


if __name__ == "__main__":
    main("0.0.0.0", 8002, agent_card_dir)