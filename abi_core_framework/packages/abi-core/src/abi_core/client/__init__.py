"""ABI-Core client-side helpers — talking TO an agent's HTTP interface.

Distinct from abi_core.agent (building agents) and abi_core.ui/abi_core.tui
(rendering frameworks): this package holds the low-level, UI-agnostic pieces
(session handling, SSE parsing) that any client — Chainlit, the TUI, a future
one — builds on instead of reimplementing.
"""
