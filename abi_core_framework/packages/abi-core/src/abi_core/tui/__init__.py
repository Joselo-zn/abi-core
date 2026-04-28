"""
abi_core.tui — Reusable Textual TUI components for ABI projects.

Provides atomic widgets, backend services, and a composable base app
that any ABI project can extend or use directly.

Usage:
    from abi_core.tui.app import AbiConsoleApp
    app = AbiConsoleApp(project_name="My Swarm", orchestrator_url="http://localhost:8000")
    app.run()

Or import individual widgets:
    from abi_core.tui.widgets import BannerWidget, ServiceTable, LogStream
"""

from .app import AbiConsoleApp

__all__ = ["AbiConsoleApp"]
