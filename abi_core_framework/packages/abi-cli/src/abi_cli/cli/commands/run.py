"""
Run command for ABI Core CLI

Detects if the project has a TUI interface configured and launches it,
or falls back to the classic docker compose + banner flow.
"""

import click
import yaml
import platform
import socket
import multiprocessing
import os
import subprocess
from pathlib import Path
from datetime import datetime
from rich.table import Table

from .utils import console
from ..banner import ABI_BANNER


def _load_runtime() -> dict:
    """Load .abi/runtime.yaml or return empty dict."""
    path = Path(".abi/runtime.yaml")
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _detect_orchestrator_port(runtime: dict) -> int:
    """Find orchestrator web interface port.

    The /stream SSE endpoint lives on the web interface port,
    not the A2A port. Try compose.yaml first (WEB_INTERFACE_PORT),
    fall back to runtime.yaml agent port.
    """
    # Try compose.yaml for the actual web interface port
    try:
        import yaml as _yaml
        with open("compose.yaml") as f:
            compose = _yaml.safe_load(f) or {}
        for svc_name, svc_cfg in compose.get("services", {}).items():
            if "orchestrator" in svc_name.lower():
                for env in svc_cfg.get("environment", []):
                    if isinstance(env, str) and env.startswith("WEB_INTERFACE_PORT="):
                        return int(env.split("=", 1)[1])
    except Exception:
        pass

    # Fallback: runtime.yaml agent port
    for key, cfg in runtime.get("agents", {}).items():
        if "orchestrator" in key.lower() or "orchestrator" in cfg.get("name", "").lower():
            return int(cfg.get("port", 8000))
    return 8000


def _detect_ollama_host(runtime: dict) -> str:
    """Detect Ollama host from project config."""
    project_dir = runtime.get("project", {}).get("name", "").lower().replace(" ", "-").replace("_", "-")
    if project_dir:
        return f"http://{project_dir}-ollama:11434"
    return "http://localhost:11434"


def _has_tui_interface(runtime: dict) -> tuple[bool, str]:
    """Check if project has a TUI interface configured.

    Returns (enabled, entry_file_path).
    """
    iface = runtime.get("interface", {})
    if not iface.get("enabled", False):
        return False, ""
    entry = iface.get("entry", "console.py")
    if Path(entry).exists():
        return True, entry
    return False, ""


def _start_compose(build: bool, detach: bool, logs: bool) -> subprocess.Popen | None:
    """Start docker compose and return the process (detached) or None."""
    cmd_parts = ["docker", "compose"]
    if build:
        cmd_parts.extend(["up", "--build"])
    else:
        cmd_parts.append("up")

    # Always detach when TUI is active — TUI handles log display
    # For classic mode: detach unless --logs is passed
    if not logs:
        cmd_parts.append("-d")

    console.print(f"📋 Command: {' '.join(cmd_parts)}")
    console.print("🐳 Starting Docker Compose...")

    try:
        if "-d" in cmd_parts:
            result = subprocess.run(cmd_parts, check=True)
            return None
        else:
            # Attached mode — blocking
            result = subprocess.run(cmd_parts, check=True)
            return None
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Error starting project: {e}", style="red")
        return None
    except KeyboardInterrupt:
        console.print("\n🛑 Stopping project...", style="yellow")
        subprocess.run(["docker", "compose", "down"], check=False)
        return None


def _launch_tui(runtime: dict, entry: str):
    """Launch the TUI interface from the project's console.py."""
    project = runtime.get("project", {})
    project_name = project.get("name", "ABI Project")
    version = project.get("version", "")
    orch_port = _detect_orchestrator_port(runtime)
    ollama_host = _detect_ollama_host(runtime)

    try:
        from abi_core.tui import AbiConsoleApp
    except ImportError:
        console.print(
            "❌ textual not installed. Run: pip install textual",
            style="red",
        )
        return

    # Try to import the project's custom console class
    import importlib.util
    app_cls = AbiConsoleApp  # default

    spec = importlib.util.spec_from_file_location("project_console", entry)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            # Find first AbiConsoleApp subclass
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name, None)
                try:
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, AbiConsoleApp)
                        and attr is not AbiConsoleApp
                    ):
                        app_cls = attr
                        break
                except TypeError:
                    continue
        except Exception as e:
            console.print(f"⚠️ Could not load {entry}: {e}", style="yellow")

    # Always use detected ports, not hardcoded ones from console.py
    app = app_cls(
        project_name=project_name,
        project_version=version,
        orchestrator_url=f"http://localhost:{orch_port}",
        ollama_host=ollama_host,
    )
    app.run()


@click.command()
@click.option('--mode', type=click.Choice(['dev', 'prod', 'test']), default='dev', help='Run mode')
@click.option('--detach', '-d', is_flag=True, help='Run in background (no logs)')
@click.option('--build', is_flag=True, help='Build images before running')
@click.option('--logs', is_flag=True, help='Show container logs in terminal')
@click.option('--no-tui', is_flag=True, help='Skip TUI, use classic docker compose output')
def run(mode, detach, build, logs, no_tui):
    """Run the ABI project.

    If the project has a TUI interface configured (interface.enabled in
    runtime.yaml), launches the interactive dashboard. Otherwise falls
    back to the classic docker compose + banner flow.

    Use --no-tui to force classic mode even if a TUI is configured.
    """

    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    if not Path('.abi/runtime.yaml').exists():
        console.print("❌ Runtime configuration not found", style="red")
        return

    if not Path('compose.yaml').exists():
        console.print("❌ Docker Compose file not found", style="red")
        console.print("💡 Try running: abi-core create project", style="blue")
        return

    runtime = _load_runtime()
    project_name = runtime.get('project', {}).get('name', 'ABI Project')

    os.environ['ABI_MODE'] = mode
    os.environ['ABI_PROJECT'] = project_name

    has_tui, entry = _has_tui_interface(runtime)

    if has_tui and not no_tui and not logs:
        # TUI mode: start compose detached, then launch TUI
        console.print(f"🚀 Starting {project_name} in {mode} mode...")
        _start_compose(build=build, detach=True, logs=False)
        _launch_tui(runtime, entry)
    else:
        # Classic mode: banner + docker compose
        _run_classic(runtime, mode, detach, build, logs)


def _run_classic(runtime: dict, mode: str, detach: bool, build: bool, logs: bool):
    """Original run behavior — banner + docker compose."""
    project_name = runtime.get('project', {}).get('name', 'ABI Project')

    console.print(ABI_BANNER)

    hostname = socket.gethostname()
    cpu_count = multiprocessing.cpu_count()
    kernel = platform.release()
    current_time = datetime.utcnow().strftime('%a %d %b %Y %H:%M:%S UTC')

    console.print(f"🌐 [bold]ABI Node[/bold] - Connected on [bold]{project_name}[/bold]")
    console.print(f"🖥 [dim]Host:[/dim] {hostname}")
    console.print(f"🧠 [dim]CPU :[/dim] {cpu_count} cores")
    console.print(f"📦 [dim]Kernel:[/dim] {kernel}")
    console.print(f"🕒 [dim]Time:[/dim] {current_time}")
    console.print("------------------------------------------")

    table = Table(title=f"{project_name} - {mode.upper()} Mode")
    table.add_column("Service", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Port", style="green")
    table.add_column("Status", style="yellow")

    table.add_row("Main App", "FastAPI", "8000", "Starting...")

    services = runtime.get('services', {})
    for svc_name, svc_cfg in services.items():
        if svc_cfg.get('enabled', True):
            table.add_row(
                svc_cfg.get('name', svc_name),
                svc_cfg.get('type', 'unknown'),
                str(svc_cfg.get('port', 'N/A')),
                "Starting...",
            )

    agents = runtime.get('agents', {})
    for agent_name, agent_cfg in agents.items():
        table.add_row(
            agent_cfg.get('name', agent_name),
            "agent",
            str(agent_cfg.get('port', 'N/A')),
            "Starting...",
        )

    if services.get('semantic_layer') or services.get('semantic-layer'):
        table.add_row("MinIO Artifact Store", "storage", "9000", "Starting...")

    console.print(table)
    console.print()

    console.print(f"🚀 Starting {project_name} in {mode} mode...")
    _start_compose(build=build, detach=detach, logs=logs)

    if not logs and not detach:
        console.print("✅ Project started successfully!", style="green")
