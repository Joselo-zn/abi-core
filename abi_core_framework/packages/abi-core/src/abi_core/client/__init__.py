"""ABI-Core client-side helpers — talking TO an agent's HTTP interface.

Distinct from abi_core.agent (building agents) and abi_core.ui
(rendering): this package holds the low-level, UI-agnostic pieces
(session handling, SSE parsing) that any client — Chainlit or a future
one — builds on instead of reimplementing.
"""

from abi_core.client.agent_stream_client import AgentStreamClient, parse_agent_message

__all__ = ["AgentStreamClient", "parse_agent_message"]
