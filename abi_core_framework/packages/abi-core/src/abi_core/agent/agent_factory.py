"""
Agent Factory — Encapsulates all boilerplate for starting an ABI agent.

Usage in main.py:
    from my_agent import MyAgent
    from config import config, AGENT_CARD
    from abi_core.agent.agent_factory import agent_factory

    def main():
        agent_instance = MyAgent()
        return agent_factory(agent_instance, config, AGENT_CARD)

    if __name__ == '__main__':
        exit(main())

With web interface:
    from web_interface import AgentWebInterface
    return agent_factory(agent_instance, config, AGENT_CARD, web_interface_cls=AgentWebInterface)
"""

import threading
from typing import Optional, Type

from abi_core.common.utils import abi_logging


def agent_factory(
    agent_instance,
    config,
    agent_card,
    *,
    host: str = "0.0.0.0",
    web_interface_cls: Optional[Type] = None,
    interface_name: Optional[str] = None,
    log_level: Optional[str] = None,
) -> int:
    """
    Bootstrap and run an ABI agent with A2A server.

    Handles:
    - Startup logging (agent card, config, ports)
    - Optional web interface in a daemon thread
    - A2A server start
    - Graceful shutdown on KeyboardInterrupt

    Args:
        agent_instance: An already-instantiated AbiAgent subclass.
        config: The agent's AgentConfig singleton (from config.py).
        agent_card: The loaded AgentCard object (from config.py).
        host: Bind address (default "0.0.0.0").
        web_interface_cls: Optional web interface class (e.g. AgentWebInterface).
                           Must accept (agent_instance, interface_name=str) in __init__.
        interface_name: Display name for the web interface.
                        Defaults to config.AGENT_DISPLAY_NAME + " Web Interface".
        log_level: Uvicorn log level for web interface (default from config.LOG_LEVEL).

    Returns:
        int: Exit code (0 = clean shutdown, 1 = error).
    """
    from abi_core.common.a2a_server import start_server

    agent_name = config.AGENT_DISPLAY_NAME
    _log_level = (log_level or getattr(config, "LOG_LEVEL", "info")).lower()

    # ── Startup info ────────────────────────────────────────────
    abi_logging(f"[🌟] Starting {agent_name} Server")
    abi_logging(f"[🌐] Host: {host}")
    abi_logging(f"[🔌] Port: {config.AGENT_PORT}")
    abi_logging(f"[📄] Agent Card: {config.AGENT_CARD}")
    abi_logging(f"[🤖] Model: {config.MODEL_NAME}")
    abi_logging(f"[🔗] Ollama: {config.OLLAMA_HOST}")

    # ── Agent card info ─────────────────────────────────────────
    abi_logging(f"[✅] Agent card loaded: {agent_card.name}")
    abi_logging(f"[📋] Description: {agent_card.description}")
    if hasattr(agent_card, "skills") and agent_card.skills:
        tags = ", ".join(agent_card.skills[0].tags) if agent_card.skills[0].tags else "none"
        abi_logging(f"[🔧] Capabilities: {tags}")

    abi_logging(f"[🚀] {agent_name} agent initialized successfully")

    try:
        # ── Web interface (optional) ────────────────────────────
        if web_interface_cls is not None:
            _interface_name = interface_name or f"{agent_name} Web Interface"
            web_port = getattr(config, "WEB_INTERFACE_PORT", None)

            if web_port is None:
                abi_logging(
                    f"[⚠️] web_interface_cls provided but config has no WEB_INTERFACE_PORT — skipping",
                    level="warning",
                )
            else:
                import uvicorn
                import inspect

                def _start_web():
                    # Support both signatures:
                    #   (agent, interface_name=str)  — scaffolded agents
                    #   (agent)                      — orchestrator / custom
                    sig = inspect.signature(web_interface_cls.__init__)
                    params = list(sig.parameters.keys())
                    if "interface_name" in params:
                        web = web_interface_cls(agent_instance, interface_name=_interface_name)
                    else:
                        web = web_interface_cls(agent_instance)
                    abi_logging(f"[🌐] Starting {_interface_name} at {host}:{web_port}")
                    uvicorn.run(web.app, host=host, port=web_port, log_level=_log_level)

                web_thread = threading.Thread(target=_start_web, daemon=True)
                web_thread.start()
                abi_logging(f"[✅] {_interface_name} started on port {web_port}")

        # ── A2A server (blocking) ──────────────────────────────
        start_server(
            host=host,
            port=config.AGENT_PORT,
            agent_card=agent_card,
            agent=agent_instance,
        )
        return 0

    except KeyboardInterrupt:
        abi_logging(f"[🛑] {agent_name} agent stopped by user")
        return 0
    except Exception as e:
        abi_logging(f"[💥] Fatal error starting {agent_name} agent: {e}", level="error")
        return 1
