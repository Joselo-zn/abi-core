"""
AbiCore — Application runner for ABI agents.

Provides a FastAPI-style interface for starting agents:

    from abi_core import AbiCore
    from my_agent import MyAgent

    app = AbiCore()
    app.run(MyAgent())

AbiCore auto-imports ``config`` and ``AGENT_CARD`` from the agent's
``config`` package (which must be on ``PYTHONPATH`` / in the same
directory as ``main.py``).
"""

from typing import Optional, Type

from abi_core.common.utils import abi_logging


class AbiCore:
    """Application runner that bootstraps and starts an ABI agent.

    On instantiation it imports ``config`` and ``AGENT_CARD`` from the
    local ``config`` package automatically.  Call :meth:`run` with an
    agent instance to start the A2A server (and optional web interface).

    Args:
        host: Bind address (default ``"0.0.0.0"``).
        web_interface_cls: Optional web-interface class.
        interface_name: Display name for the web interface.
    """

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        web_interface_cls: Optional[Type] = None,
        interface_name: Optional[str] = None,
    ):
        self.host = host
        self.web_interface_cls = web_interface_cls
        self.interface_name = interface_name

        # Auto-import config and AGENT_CARD from the agent's config package
        try:
            import config as _cfg_module
            self.config = _cfg_module.config
            self.agent_card = _cfg_module.AGENT_CARD
        except ImportError as e:
            raise ImportError(
                "AbiCore requires a 'config' package with 'config' and "
                "'AGENT_CARD' exports. Make sure config/ is on PYTHONPATH."
            ) from e
        except AttributeError as e:
            raise AttributeError(
                "The 'config' package must export both 'config' (AgentConfig) "
                "and 'AGENT_CARD' (AgentCard)."
            ) from e

    def run(self, agent_instance) -> int:
        """Start the agent with A2A server and optional web interface.

        Args:
            agent_instance: An already-instantiated AbiAgent subclass.

        Returns:
            Exit code (0 = clean shutdown, 1 = error).
        """
        from abi_core.agent.agent_factory import agent_factory

        return agent_factory(
            agent_instance,
            self.config,
            self.agent_card,
            host=self.host,
            web_interface_cls=self.web_interface_cls,
            interface_name=self.interface_name,
        )
