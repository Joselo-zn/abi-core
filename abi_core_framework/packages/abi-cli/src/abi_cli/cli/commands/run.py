"""
Run command for ABI Core CLI — banner + docker compose.
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


def _ensure_shared_resources() -> None:
    """Create shared Docker resources if they don't exist.

    - ollama_data volume: shared across all ABI projects
    - abi-network: shared Docker network (created by compose, but volume must pre-exist)
    """
    # Create ollama_data volume if it doesn't exist
    result = subprocess.run(
        ["docker", "volume", "inspect", "ollama_data"],
        capture_output=True,
    )
    if result.returncode != 0:
        console.print("📦 Creating shared ollama_data volume...", style="dim")
        subprocess.run(["docker", "volume", "create", "ollama_data"], check=True)
        console.print("✅ ollama_data volume created", style="dim")


def _start_compose(build: bool, detach: bool, logs: bool) -> bool:
    """Start docker compose. Returns True on success, False on failure."""
    # Ensure shared resources exist before starting
    _ensure_shared_resources()

    cmd_parts = ["docker", "compose"]
    if build:
        cmd_parts.extend(["up", "--build"])
    else:
        cmd_parts.append("up")

    # Detach unless --logs is passed
    if not logs:
        cmd_parts.append("-d")

    console.print(f"📋 Command: {' '.join(cmd_parts)}")
    console.print("🐳 Starting Docker Compose...")

    try:
        subprocess.run(cmd_parts, check=True)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Error starting project: {e}", style="red")
        return False
    except KeyboardInterrupt:
        console.print("\n🛑 Stopping project...", style="yellow")
        subprocess.run(["docker", "compose", "down"], check=False)
        return False


@click.command()
@click.option('--detach', '-d', is_flag=True, help='Run in background (no logs)')
@click.option('--build', is_flag=True, help='Build images before running')
@click.option('--logs', is_flag=True, help='Show container logs in terminal')
def run(detach, build, logs):
    """Run the ABI project (docker compose)."""

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

    os.environ['ABI_PROJECT'] = project_name

    _run_classic(runtime, detach, build, logs)


def _run_classic(runtime: dict, detach: bool, build: bool, logs: bool):
    """Banner + docker compose."""
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

    table = Table(title=project_name)
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

    console.print(f"🚀 Starting {project_name}...")
    started = _start_compose(build=build, detach=detach, logs=logs)

    if started and not logs and not detach:
        console.print("✅ Project started successfully!", style="green")
