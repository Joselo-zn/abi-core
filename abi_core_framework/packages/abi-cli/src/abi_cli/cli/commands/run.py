"""
Run command for ABI Core CLI
"""

import click
import yaml
import platform
import socket
import multiprocessing
from pathlib import Path
from datetime import datetime
from rich.table import Table

from .utils import console
from ..banner import ABI_BANNER


@click.command()
@click.option('--mode', type=click.Choice(['dev', 'prod', 'test']), default='dev', help='Run mode')
@click.option('--detach', '-d', is_flag=True, help='Run in background')
@click.option('--build', is_flag=True, help='Build images before running')
def run(mode, detach, build):
    """Run the ABI project"""
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return
    
    runtime_file = Path('.abi/runtime.yaml')
    compose_file = Path('compose.yaml')
    
    if not runtime_file.exists():
        console.print("❌ Runtime configuration not found", style="red")
        return
    
    # Load runtime configuration
    with open(runtime_file, 'r') as f:
        runtime_config = yaml.safe_load(f)
    
    # Show ABI Banner and system info
    console.print(ABI_BANNER, style="cyan")
    
    # Get system information
    project_name = runtime_config.get('project', {}).get('name', 'ABI Project')
    hostname = socket.gethostname()
    cpu_count = multiprocessing.cpu_count()
    kernel = platform.release()
    current_time = datetime.utcnow().strftime('%a %d %b %Y %H:%M:%S UTC')
    
    # System info in ABI format
    console.print(f"🌐 [bold]ABI Node[/bold] - Connected on [bold]{project_name}[/bold]")
    console.print(f"🖥 [dim]Host:[/dim] {hostname}")
    console.print(f"🧠 [dim]CPU :[/dim] {cpu_count} cores")
    console.print(f"📦 [dim]Kernel:[/dim] {kernel}")
    console.print(f"🕒 [dim]Time:[/dim] {current_time}")
    console.print("------------------------------------------")
    
    # Show services that will be started
    table = Table(title=f"{project_name} - {mode.upper()} Mode")
    table.add_column("Service", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Port", style="green")
    table.add_column("Status", style="yellow")
    
    # Add main service
    table.add_row("Main App", "FastAPI", "8000", "Starting...")
    
    # Add configured services
    services = runtime_config.get('services', {})
    for service_name, service_config in services.items():
        if service_config.get('enabled', True):
            table.add_row(
                service_config.get('name', service_name),
                service_config.get('type', 'unknown'),
                str(service_config.get('port', 'N/A')),
                "Starting..."
            )
    
    console.print(table)
    console.print()
    
    # Build Docker Compose command
    cmd_parts = ["docker", "compose"]
    
    if build:
        cmd_parts.extend(["up", "--build"])
    else:
        cmd_parts.append("up")
    
    if detach:
        cmd_parts.append("-d")
    
    # Set environment variables for the mode
    import os
    os.environ['ABI_MODE'] = mode
    os.environ['ABI_PROJECT'] = project_name
    
    console.print(f"🚀 Starting {project_name} in {mode} mode...")
    console.print(f"📋 Command: {' '.join(cmd_parts)}")
    
    if compose_file.exists():
        console.print("🐳 Using Docker Compose...")
        
        # Execute docker compose
        import subprocess
        try:
            result = subprocess.run(cmd_parts, check=True)
            if result.returncode == 0:
                console.print("✅ Project started successfully!", style="green")
                if not detach:
                    console.print("Press Ctrl+C to stop", style="dim")
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Error starting project: {e}", style="red")
        except KeyboardInterrupt:
            console.print("\n🛑 Stopping project...", style="yellow")
            subprocess.run(["docker", "compose", "down"], check=False)
    else:
        console.print("❌ Docker Compose file not found", style="red")
        console.print("💡 Try running: abi-core create project", style="blue")