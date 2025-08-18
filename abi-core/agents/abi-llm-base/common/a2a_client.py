import json
import logging
import sys

import httpx
import uvicorn

from starlette.routing import Route
from starlette.applications import Starlette

from a2a.types import AgentCard
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)

from pathlib import Path

from agent.agent import Agent
from common.agent_executor import ABIAgentExecutor

logger = logging.getLogger(__name__)


def _attach_health_route(app: Starlette) -> None:
    """Add and Endpoint /health to the Starlette app/ASGI."""
    async def health(_request):
        return app.respose_class(
            content=json.dumps({"ok": True}),
            status_code=200,
            media_type="application/json"
        )

    try:
        app.router.routes.append(
            Route("/health", 
                  endpoint=health,
                  methods=["GET"]
                  )
            )
    except Exception as e:
        logger.warning(f'[!] Could not attache health route {e}')


def start_server(host: str, port: int, agent_card: json, agent: Agent):
    """Starts A2A agent server
    Parasm:
        host: Agent host in string format
        port: Agent port in int format
        agent_card: Agent Card in JSON format
        agent: agent class
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
            config_store=push_notification_config_store
        )

        request_handler = DefaultRequestHandler(
            agent_executor=ABIAgentExecutor(agent=agent),
            task_store=InMemoryTaskStore(),
            push_config_store=push_notification_config_store,
            push_sender=push_notification_sender
        )

        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        asgi_app = a2a_app.build()
        _attach_health_route(asgi_app)

        logger.info(f'[🚀] Starting A2A {agent_card.name} Client on {host}:{port}')
        uvicorn.run(asgi_app, host=host, port=port)

    except FileNotFoundError:
        logger.error(f"Error: File '{agent_card}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error: File '{agent_card}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)