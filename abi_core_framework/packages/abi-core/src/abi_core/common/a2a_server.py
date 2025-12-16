import json
import logging
import sys
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route,  Mount, WebSocketRoute

from a2a.types import AgentCard
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)

from abi_core.agent.agent import AbiAgent
from abi_core.common.agent_executor import ABIAgentExecutor

logger = logging.getLogger(__name__)

def _attach_card_route(app: Starlette, card_dict: dict) -> None:
    async def card(_request):
        return JSONResponse(card_dict, status_code=200)
    app.add_route("/card", card, methods=["GET"])

def _attach_routes_route(app: Starlette) -> None:
    def _collect(r, base=""):
        items = []
        if isinstance(r, Route):
            items.append({"path": base + r.path, "methods": sorted(list(r.methods or [])), "name": r.name})
        elif isinstance(r, WebSocketRoute):
            items.append({"path": base + r.path, "methods": ["WEBSOCKET"], "name": r.name})
        elif isinstance(r, Mount):
            for sr in r.routes:
                items.extend(_collect(sr, base + r.path))
        return items

    async def routes(_request):
        items = []
        for r in app.routes:
            items.extend(_collect(r, ""))
        # opcional: ordena por path
        items.sort(key=lambda x: x["path"])
        return JSONResponse(items, status_code=200)

    app.add_route("/__routes", routes, methods=["GET"])

def _attach_root_head(app: Starlette) -> None:
    async def root_head(_request):
        return JSONResponse({}, status_code=200)
    app.add_route("/", root_head, methods=["HEAD"])

def _attach_health_route(app: Starlette) -> None:
    """Añade /health a la app Starlette/ASGI."""
    async def health(_request):
        return JSONResponse({"ok": True}, status_code=200)

    try:
        app.add_route("/health", health, methods=["GET"])
    except Exception as e:
        logger.warning(f"[!] Could not attach /health route: {e}")

def start_server(host: str, port: int, agent_card, agent: AbiAgent):
    """
    Starts A2A server agent
    
    Args:
        host: Host to bind to
        port: Port to bind to
        agent_card: Either AgentCard object or path to agent card JSON file (str)
        agent: AbiAgent instance
    """
    try:
        if not agent_card:
            raise ValueError("[!] Abi Agent card is required")

        # Handle both AgentCard object and file path
        if isinstance(agent_card, AgentCard):
            agent_card_obj = agent_card
            # Convert AgentCard to dict for the card route
            card_dict = agent_card_obj.model_dump()
        elif isinstance(agent_card, (str, Path)):
            with Path(agent_card).open("r", encoding="utf-8") as f:
                card_dict = json.load(f)
            agent_card_obj = AgentCard(**card_dict)
        else:
            raise TypeError(f"agent_card must be AgentCard or str/Path, got {type(agent_card)}")

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
        _attach_root_head(asgi_app)
        _attach_card_route(asgi_app, card_dict)
        _attach_routes_route(asgi_app) 

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
