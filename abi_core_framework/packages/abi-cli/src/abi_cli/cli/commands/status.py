"""
Status command for ABI Core CLI
"""

import click
import yaml
from pathlib import Path
from rich.table import Table
from rich.panel import Panel

from .utils import console


@click.command()
def status():
    """Show project status and running services"""
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        console.print("💡 Run this command from inside a project created with:", style="yellow")
        console.print("   abi-core create project my-project --domain 'General'", style="cyan")
        return
    
    runtime_file = Path('.abi/runtime.yaml')
    
    if not runtime_file.exists():
        console.print("❌ Runtime configuration not found (.abi/runtime.yaml)", style="red")
        console.print("💡 This appears to be an incomplete ABI project.", style="yellow")
        console.print("   Try creating a new project with:", style="yellow")
        console.print("   abi-core create project my-project --domain 'General'", style="cyan")
        return
    
    # Load runtime configuration
    try:
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f)
        
        if runtime_config is None:
            console.print("❌ Runtime configuration is empty or invalid", style="red")
            return
    except yaml.YAMLError as e:
        console.print(f"❌ Error parsing runtime configuration: {e}", style="red")
        return
    
    project_info = runtime_config.get('project', {})
    project_name = project_info.get('name', 'Unknown Project')
    
    # Project overview
    overview_panel = Panel.fit(
        f"""[cyan]Project:[/cyan] {project_name}
[cyan]Domain:[/cyan] {project_info.get('domain', 'general')}
[cyan]Mode:[/cyan] {runtime_config.get('runtime', {}).get('mode', 'development')}""",
        title="📊 Project Overview",
        border_style="blue"
    )
    console.print(overview_panel)
    
    # Agents status
    agents = runtime_config.get('agents', {})
    if agents:
        agents_table = Table(title="🤖 Agents")
        agents_table.add_column("Name", style="cyan")
        agents_table.add_column("Description", style="white")
        agents_table.add_column("Model", style="green")
        agents_table.add_column("Port", style="yellow")
        
        for agent_key, agent_config in agents.items():
            agents_table.add_row(
                agent_config.get('name', agent_key),
                agent_config.get('description', 'N/A')[:50] + "..." if len(agent_config.get('description', '')) > 50 else agent_config.get('description', 'N/A'),
                agent_config.get('model', 'N/A'),
                str(agent_config.get('port', 'N/A'))
            )
        
        console.print(agents_table)
    else:
        console.print("🤖 [dim]No agents configured[/dim]")
    
    # Services status
    services = runtime_config.get('services', {})
    if services:
        services_table = Table(title="⚙️ Services")
        services_table.add_column("Name", style="cyan")
        services_table.add_column("Type", style="magenta")
        services_table.add_column("Port", style="green")
        services_table.add_column("Domain", style="yellow")
        services_table.add_column("Status", style="white")
        
        for service_key, service_config in services.items():
            status = "🟢 Enabled" if service_config.get('enabled', True) else "🔴 Disabled"
            services_table.add_row(
                service_config.get('name', service_key),
                service_config.get('type', 'unknown'),
                str(service_config.get('port', 'N/A')),
                service_config.get('domain', 'general'),
                status
            )
        
        console.print(services_table)
    else:
        console.print("⚙️ [dim]No services configured[/dim]")
    
    # Policies status
    policies = runtime_config.get('policies', {})
    if policies:
        policies_table = Table(title="🛡️ Security Policies")
        policies_table.add_column("Name", style="cyan")
        policies_table.add_column("Domain", style="yellow")
        policies_table.add_column("File", style="green")
        
        for policy_key, policy_config in policies.items():
            policies_table.add_row(
                policy_config.get('name', policy_key),
                policy_config.get('domain', 'general'),
                policy_config.get('file', 'N/A')
            )
        
        console.print(policies_table)
    else:
        console.print("🛡️ [dim]No custom policies configured[/dim]")
    
    # Check for running Docker containers
    console.print("\n🐳 [bold]Docker Status[/bold]")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "table"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            console.print(result.stdout)
        else:
            console.print("[dim]No running containers found[/dim]")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        console.print("[dim]Docker not available or not responding[/dim]")
    
    # Summary
    total_agents = len(agents)
    total_services = len(services)
    total_policies = len(policies)
    
    summary_panel = Panel.fit(
        f"""[green]✅ Agents:[/green] {total_agents} configured
[blue]⚙️ Services:[/blue] {total_services} configured  
[yellow]🛡️ Policies:[/yellow] {total_policies} configured""",
        title="📋 Summary",
        border_style="green"
    )
    console.print(summary_panel)