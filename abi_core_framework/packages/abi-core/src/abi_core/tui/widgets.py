"""
abi_core.tui.widgets — Reusable Textual widgets for ABI dashboards.

Each widget is self-contained and can be used independently.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone

from textual.widgets import Static, RichLog, DataTable, Input
from textual.containers import Container
from textual.message import Message


# ── Banner ───────────────────────────────────────────────────────

_BANNER_TEMPLATE = """\
[bold bright_cyan] █████╗   ██████╗   ██╗[/]  {title}
[bold bright_cyan]██╔══██╗  ██╔══██╗  ██║[/]  {subtitle}
[bold bright_cyan]███████║  ██████╔╝  ██║[/]  🌐 Nodes: {nodes}
[bold bright_cyan]██╔══██║  ██╔══██╗  ██║[/]  🖥  Host: {host}
[bold bright_cyan]██║  ██║  ██████╔╝  ██║[/]  🕒 {time}
[bold bright_cyan]╚═╝  ╚═╝   ╚════╝   ╚═╝[/]"""


class BannerWidget(Static):
    """Top-left banner showing project info and system stats."""

    def __init__(
        self,
        title: str = "ABI Swarm",
        subtitle: str = "",
        **kwargs,
    ):
        super().__init__("", **kwargs)
        self._title = title
        self._subtitle = subtitle

    def refresh_banner(self, node_count: int = 0) -> None:
        now = datetime.now(timezone.utc).strftime("%a %d %b %Y %H:%M:%S UTC")
        text = _BANNER_TEMPLATE.format(
            title=self._title,
            subtitle=self._subtitle,
            nodes=node_count,
            host=socket.gethostname(),
            time=now,
        )
        self.update(text)

    def on_mount(self) -> None:
        self.refresh_banner()


# ── Service Table ────────────────────────────────────────────────

_STATUS_ICONS = {
    "running": "[green]●[/] running",
    "exited": "[red]●[/] exited",
    "created": "[yellow]●[/] created",
    "restarting": "[yellow]●[/] restarting",
    "stopped": "[red]●[/] stopped",
}


class ServiceTable(DataTable):
    """Table showing Docker services with status indicators."""

    def on_mount(self) -> None:
        self.add_columns("Service", "Type", "Port", "Status")
        self.cursor_type = "row"

    def refresh_services(self, services: list[dict]) -> None:
        self.clear()
        for svc in services:
            status = _STATUS_ICONS.get(svc.get("status", ""), svc.get("status", ""))
            self.add_row(
                svc.get("name", ""),
                svc.get("type", ""),
                svc.get("port", ""),
                status,
            )


# ── Log Stream ───────────────────────────────────────────────────

class LogStream(RichLog):
    """Scrollable log panel that accepts append_log() calls."""

    def append_log(self, line: str) -> None:
        self.write(line)


# ── Conversation Panel ───────────────────────────────────────────

class ConversationPanel(RichLog):
    """Right-side panel showing the conversation with the orchestrator."""

    def add_user_message(self, text: str) -> None:
        self.write(f"[bold cyan]> {text}[/]")

    def add_system_message(self, text: str) -> None:
        self.write(f"[dim]{text}[/]")

    def add_event(self, text: str) -> None:
        self.write(text)


# ── Command Input ────────────────────────────────────────────────

class CommandInput(Input):
    """Input bar at the bottom. Emits CommandSubmitted on Enter."""

    class CommandSubmitted(Message):
        """Fired when the user presses Enter."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, **kwargs):
        super().__init__(
            placeholder="> Type a command or message...",
            **kwargs,
        )

    def action_submit(self) -> None:
        text = self.value.strip()
        if text:
            self.post_message(self.CommandSubmitted(text))
            self.value = ""
