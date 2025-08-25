import json
import logging
import sys
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route  # opcional si usas add_route

from a2a.types import AgentCard
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)

from agent.agent import Agent
from common.agent_executor import ABIAgentExecutor

logger = logging.getLogger(__name__)

def _attach_health_route(app: Starlette) -> None:
    """Añade /health a la app Starlette/ASGI."""
    async def health(_request):
        return JSONResponse({"ok": True}, status_code=200)

    try:
        app.add_route("/health", health, methods=["GET"])
    except Exception as e:
        logger.warning(f"[!] Could not attach /health route: {e}")

def start_client(host: str, port: int, agent_card: str, agent: Agent):
    """Starts A2A client agent"""
    try:
        if not agent_card:
            raise ValueError("[!] Abi Agent card is required")

        with Path(agent_card).open("r", encoding="utf-8") as f:
            data = json.load(f)
        agent_card_obj = AgentCard(**data)

        # Nota: httpx.AsyncClient no se cierra aquí (MVP); idealmente cerrarlo en lifespan
        client = httpx.AsyncClient()
        push_cfg_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(
            client,
            config_store=push_cfg_store,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=ABIAgentExecutor(agent=agent),
            task_store=InMemoryTaskStore(),
            push_config_store=push_cfg_store,
            push_sender=push_sender,
        )

        a2a_app = A2AStarletteApplication(
            agent_card=agent_card_obj,
            http_handler=request_handler,
        )
        asgi_app = a2a_app.build()
        _attach_health_route(asgi_app)

        logger.info(f"[🚀] Starting A2A {agent_card_obj.name} Client on {host}:{port}")
        uvicorn.run(asgi_app, host=host, port=port)

    except FileNotFoundError:
        logger.error(f"Error: File '{agent_card}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error: File '{agent_card}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}", exc_info=True)
        sys.exit(1)
