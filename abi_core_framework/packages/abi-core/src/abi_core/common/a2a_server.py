import json
import sys
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount, WebSocketRoute

from a2a.types import AgentCard
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.agent_card_routes import create_agent_card_routes

from abi_core.agent.agent import AbiAgent
from abi_core.common.agent_executor import ABIAgentExecutor
from abi_core.common.agent_card_loader import load_agent_card, get_agent_url
from abi_core.common.utils import abi_logging


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
        abi_logging(f"[!] Could not attach /health route: {e}", level="warning")


def _attach_audit_route(app: Starlette) -> None:
    """POST /audit/log — receive and persist audit events from A2A validators."""
    async def audit_log(request):
        try:
            data = await request.json()
            event_type = data.get("event_type", "unknown")
            source = data.get("source_agent", "unknown")
            target = data.get("target_agent", "unknown")
            allowed = data.get("allowed", None)
            reason = data.get("reason", "")
            abi_logging(
                f"[📋 AUDIT] {event_type}: {source} → {target} | allowed={allowed} | {reason}"
            )
            return JSONResponse({"status": "logged"}, status_code=200)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    try:
        app.add_route("/audit/log", audit_log, methods=["POST"])
    except Exception as e:
        abi_logging(f"[!] Could not attach /audit/log route: {e}", level="warning")


def start_server(host: str, port: int, agent_card, agent: AbiAgent):
    """
    Starts A2A server agent.

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
            card_dict = {"name": agent_card_obj.name, "description": agent_card_obj.description}
        elif isinstance(agent_card, (str, Path)):
            with Path(agent_card).open("r", encoding="utf-8") as f:
                card_dict = json.load(f)
            agent_card_obj, _abi_meta = load_agent_card(str(agent_card))
        else:
            raise TypeError(f"agent_card must be AgentCard or str/Path, got {type(agent_card)}")

        # Build request handler
        push_cfg_store = InMemoryPushNotificationConfigStore()
        task_store = InMemoryTaskStore()

        request_handler = DefaultRequestHandler(
            agent_executor=ABIAgentExecutor(agent=agent),
            task_store=task_store,
            agent_card=agent_card_obj,
            push_config_store=push_cfg_store,
        )

        # Build Starlette app with A2A routes
        a2a_routes = create_jsonrpc_routes(request_handler, rpc_url="/")
        card_routes = create_agent_card_routes(agent_card_obj)
        all_routes = a2a_routes + card_routes

        asgi_app = Starlette(routes=all_routes)
        _attach_health_route(asgi_app)
        _attach_root_head(asgi_app)
        _attach_card_route(asgi_app, card_dict)
        _attach_audit_route(asgi_app)
        _attach_routes_route(asgi_app)

        abi_logging(f"[🚀] Starting A2A {agent_card_obj.name} Client on {host}:{port}")
        uvicorn.run(asgi_app, host=host, port=port)

    except FileNotFoundError:
        abi_logging(f"Error: File '{agent_card}' not found.", level="error")
        sys.exit(1)
    except json.JSONDecodeError:
        abi_logging(f"Error: File '{agent_card}' contains invalid JSON.", level="error")
        sys.exit(1)
    except Exception as e:
        abi_logging(f"An error occurred during server startup: {e}", level="error")
        sys.exit(1)
