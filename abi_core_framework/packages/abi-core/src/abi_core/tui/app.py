"""
abi_core.tui.app — Composable Textual dashboard for ABI projects.

Layout (matches spec):
  ┌──────────────────────────────┬──────────────────┐
  │  Banner + System Info        │                  │
  ├──────────────────────────────┤  Services Table  │
  │  Conversation / Chat         │                  │
  ├──────────────────────────────┴──────────────────┤
  │  > Input                                        │
  ├─────────────────────────────────────────────────┤
  │  Log Stream                                     │
  └─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import yaml
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual import work

from .widgets import (
    BannerWidget,
    ServiceTable,
    LogStream,
    ConversationPanel,
    CommandInput,
)
from .services import DockerService, OllamaService, OrchestratorClient


class AbiConsoleApp(App):
    """Base interactive console for any ABI project."""

    TITLE = "ABI Console"

    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }

    #top-section {
        layout: horizontal;
        height: 1fr;
        min-height: 10;
        max-height: 22;
    }

    #left-column {
        layout: vertical;
        width: 2fr;
    }

    #banner {
        height: auto;
        padding: 0 1;
        border: solid $primary;
    }

    #services {
        width: 1fr;
        border: solid $secondary;
    }

    #conversation {
        height: 1fr;
        border: solid $accent;
    }

    #cmd-input {
        height: 3;
    }

    #log-stream {
        height: 1fr;
        min-height: 6;
        border: solid $primary;
    }

    DataTable > .datatable--header {
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_logs", "Clear Logs", show=True),
        Binding("ctrl+r", "refresh_status", "Refresh", show=True),
    ]

    def __init__(
        self,
        project_name: str = "ABI Project",
        project_version: str = "",
        orchestrator_url: str = "http://localhost:8000",
        ollama_host: str = "http://localhost:11434",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_name = project_name
        self.project_version = project_version
        self._orchestrator_url = orchestrator_url

        # Backend services
        self.docker_svc = DockerService()
        self.ollama_svc = OllamaService(host=ollama_host)
        self.orchestrator = OrchestratorClient(url=orchestrator_url)

        # Load expected services from runtime.yaml
        self._expected_services = self._load_expected_services()

    def _load_expected_services(self) -> list[dict]:
        """Load expected services from .abi/runtime.yaml."""
        runtime_path = Path(".abi/runtime.yaml")
        if not runtime_path.exists():
            return []
        try:
            with open(runtime_path) as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            return []

        expected = []
        # Services section
        for key, svc in cfg.get("services", {}).items():
            if svc.get("enabled", True):
                expected.append({
                    "name": svc.get("name", key),
                    "type": svc.get("type", "service"),
                    "port": str(svc.get("port", "")),
                    "config_key": key,
                })
        # Agents section
        for key, agent in cfg.get("agents", {}).items():
            expected.append({
                "name": agent.get("name", key),
                "type": "agent",
                "port": str(agent.get("port", "")),
                "config_key": key,
            })
        return expected

    # ── Layout ───────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        subtitle = f"OSS CLI v{self.project_version}" if self.project_version else ""
        with Horizontal(id="top-section"):
            with Vertical(id="left-column"):
                yield BannerWidget(
                    title=f"{self.project_name} — Interactive Console",
                    subtitle=subtitle,
                    id="banner",
                )
                yield ConversationPanel(id="conversation", markup=True, wrap=True)
            yield ServiceTable(id="services")
        yield CommandInput(id="cmd-input")
        yield LogStream(id="log-stream", markup=True, wrap=True)

    # ── Lifecycle ─────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._refresh_all()
        self.set_interval(5, self._refresh_all)
        # Auto-start log streaming for all compose services
        self._start_log_streaming()

    def _refresh_all(self) -> None:
        """Refresh banner + service table with real Docker status."""
        # Derive compose project name from project_name
        project_filter = self.project_name.lower().replace(" ", "").replace("-", "").replace("_", "")

        running_containers = self.docker_svc.list_services(
            project_filter=project_filter
        )
        running_count = sum(
            1 for c in running_containers if c.get("status") == "running"
        )

        banner: BannerWidget = self.query_one("#banner", BannerWidget)
        banner.refresh_banner(node_count=running_count)

        # Build lookup: compose service name -> container data
        # Docker may prefix service names with project name (e.g. "abejas-orchestrator")
        container_by_service: dict[str, dict] = {}
        for c in running_containers:
            svc = c["name"].lower()
            container_by_service[svc] = c
            # Also store without project prefix for matching
            if svc.startswith(project_filter + "-"):
                short = svc[len(project_filter) + 1:]
                container_by_service[short] = c

        service_rows = []
        for svc in self._expected_services:
            config_key = svc["config_key"].lower()
            variants = {
                config_key,
                config_key.replace("_", "-"),
                config_key.replace("-", "_"),
                f"{project_filter}-{config_key}",
                f"{project_filter}-{config_key.replace('_', '-')}",
            }
            status = "stopped"
            for v in variants:
                if v in container_by_service:
                    status = container_by_service[v].get("status", "unknown")
                    break
            service_rows.append({
                "name": svc["name"],
                "type": svc["type"],
                "port": svc["port"],
                "status": status,
            })

        table: ServiceTable = self.query_one("#services", ServiceTable)
        table.refresh_services(service_rows)

    # ── Actions ──────────────────────────────────────────────────

    def action_clear_logs(self) -> None:
        self.query_one("#log-stream", LogStream).clear()

    def action_refresh_status(self) -> None:
        self._refresh_all()

    # ── Log streaming ────────────────────────────────────────────

    @work(group="log-stream")
    async def _start_log_streaming(self) -> None:
        """Stream docker compose logs into the log panel."""
        log: LogStream = self.query_one("#log-stream", LogStream)

        if not self.docker_svc.available:
            log.append_log("[yellow]Docker not available — logs disabled[/]")
            return

        log.append_log("[dim]Streaming Docker Compose logs...[/]")

        try:
            async for line in self.docker_svc.stream_compose_logs(tail=50):
                log.append_log(line)
        except Exception as e:
            log.append_log(f"[red]Log stream error: {e}[/]")
            log.append_log("[dim]Tip: type 'logs <service-name>' to stream a specific container[/]")

    # ── Command handling ─────────────────────────────────────────

    def on_command_input_command_submitted(
        self, event: CommandInput.CommandSubmitted
    ) -> None:
        text = event.value
        log: LogStream = self.query_one("#log-stream", LogStream)
        conv: ConversationPanel = self.query_one("#conversation", ConversationPanel)

        parts = text.split(None, 1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "status":
            self._refresh_all()
            log.append_log("[dim]Status refreshed[/]")

        elif cmd == "models":
            self._handle_models(log)

        elif cmd == "ephemeral":
            self._handle_ephemeral(arg, log)

        elif cmd == "logs":
            if arg:
                self._handle_logs(arg, log)
            else:
                log.append_log("[yellow]Usage: logs <container-name>[/]")

        elif cmd == "ask":
            if arg:
                conv.add_user_message(arg)
                self._handle_ask(arg, conv, log)
            else:
                log.append_log("[yellow]Usage: ask <your question>[/]")

        elif cmd == "cleanup":
            n = self.docker_svc.cleanup_ephemeral()
            log.append_log(f"🗑️ Removed {n} stopped ephemeral containers")

        elif cmd == "help":
            log.append_log(
                "[bold]Commands:[/] status, ask <msg>, logs <name>, "
                "models, ephemeral, cleanup, help, quit"
            )

        elif cmd in ("quit", "exit"):
            self.exit()

        else:
            # Default: treat as ask
            conv.add_user_message(text)
            self._handle_ask(text, conv, log)

    # ── Workers ──────────────────────────────────────────────────

    @work(exclusive=True, group="models")
    async def _handle_models(self, log: LogStream) -> None:
        models = await self.ollama_svc.list_models()
        if not models:
            log.append_log("[dim]No models found or Ollama unreachable[/]")
            return
        for m in models:
            log.append_log(f"  {m['name']}  ({m['size']})")

    @work(exclusive=True, group="ephemeral")
    async def _handle_ephemeral(self, arg: str, log: LogStream) -> None:
        ephemerals = self.docker_svc.list_ephemeral()
        if not ephemerals:
            log.append_log("[dim]No ephemeral containers[/]")
            return
        for e in ephemerals:
            log.append_log(f"  {e['name']}  [{e['status']}]")

    @work(exclusive=True, group="single-log")
    async def _handle_logs(self, name: str, log: LogStream) -> None:
        log.append_log(f"[dim]Streaming logs from {name}...[/]")
        async for line in self.docker_svc.stream_logs(name, tail=30):
            log.append_log(line)

    @work(exclusive=True, group="ask")
    async def _handle_ask(
        self, query: str, conv: ConversationPanel, log: LogStream
    ) -> None:
        conv.add_system_message("⏳ Sending to orchestrator...")
        async for event in self.orchestrator.ask(query):
            evt_type = event.get("event", "")
            data = event.get("data", "")

            if evt_type == "done":
                conv.add_system_message("✅ Done")
                break
            elif evt_type == "error":
                conv.add_system_message(f"[red]❌ {data}[/]")
                break
            else:
                if isinstance(data, dict):
                    # Show meaningful fields in conversation
                    msg = (
                        data.get("message", "")
                        or data.get("text", "")
                        or data.get("result", "")
                    )
                    if msg:
                        conv.add_event(str(msg))
                    else:
                        # Show the full dict if no known field
                        conv.add_event(str(data))
                    log.append_log(f"[dim]{data}[/]")
                elif data:
                    conv.add_event(str(data))


# ── Standalone entry point ───────────────────────────────────────

def run_console(
    project_name: str = "ABI Swarm",
    project_version: str = "",
    orchestrator_url: str = "http://localhost:8000",
    ollama_host: str = "http://localhost:11434",
) -> None:
    """Launch the console app. Can be called from any project's main."""
    app = AbiConsoleApp(
        project_name=project_name,
        project_version=project_version,
        orchestrator_url=orchestrator_url,
        ollama_host=ollama_host,
    )
    app.run()
