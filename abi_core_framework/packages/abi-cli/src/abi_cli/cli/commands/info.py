"""
Info command for ABI Core CLI
"""

import click
import yaml
from pathlib import Path
from rich.panel import Panel
from rich.table import Table

from .utils import console


@click.command()
def info():
    """Show project information"""
    
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        return
    
    runtime_file = Path('.abi/runtime.yaml')
    if runtime_file.exists():
        with open(runtime_file, 'r') as f:
            config = yaml.safe_load(f)
        
        project_info = config.get('project', {})
        runtime_info = config.get('runtime', {})
        
        # Main project information
        main_panel = Panel.fit(
            f"""[cyan]Project:[/cyan] {project_info.get('name', 'Unknown')}
[cyan]Description:[/cyan] {project_info.get('description', 'N/A')}
[cyan]Domain:[/cyan] {project_info.get('domain', 'general')}
[cyan]Version:[/cyan] {project_info.get('version', '1.0.0')}
[cyan]Mode:[/cyan] {runtime_info.get('mode', 'development')}
[cyan]Log Level:[/cyan] {runtime_info.get('log_level', 'INFO')}""",
            title="📋 Project Information",
            border_style="blue"
        )
        console.print(main_panel)
        
        # Port configuration
        ports_info = runtime_info.get('ports', {})
        if ports_info:
            ports_panel = Panel.fit(
                f"""[cyan]Start Port:[/cyan] {ports_info.get('start', 8000)}
[cyan]End Port:[/cyan] {ports_info.get('end', 8100)}""",
                title="🔌 Port Configuration",
                border_style="green"
            )
            console.print(ports_panel)
        
        # Components summary
        agents_count = len(config.get('agents', {}))
        services_count = len(config.get('services', {}))
        policies_count = len(config.get('policies', {}))
        
        components_table = Table(title="📦 Components Summary")
        components_table.add_column("Component", style="cyan")
        components_table.add_column("Count", style="green")
        components_table.add_column("Status", style="yellow")
        
        components_table.add_row("Agents", str(agents_count), "🤖 Configured" if agents_count > 0 else "❌ None")
        components_table.add_row("Services", str(services_count), "⚙️ Configured" if services_count > 0 else "❌ None")
        components_table.add_row("Policies", str(policies_count), "🛡️ Configured" if policies_count > 0 else "❌ None")
        
        console.print(components_table)
        
        # File structure info
        project_files = []
        
        # Check for key files
        key_files = [
            ('main.py', 'Main application'),
            ('requirements.txt', 'Dependencies'),
            ('compose.yaml', 'Docker Compose'),
            ('Dockerfile', 'Docker image'),
            ('README.md', 'Documentation')
        ]
        
        for filename, description in key_files:
            if Path(filename).exists():
                project_files.append(f"✅ {filename} - {description}")
            else:
                project_files.append(f"❌ {filename} - {description}")
        
        # Check directories
        key_dirs = [
            ('agents/', 'Agents directory'),
            ('services/', 'Services directory'),
            ('policies/', 'Policies directory'),
            ('config/', 'Configuration directory')
        ]
        
        for dirname, description in key_dirs:
            if Path(dirname).exists():
                project_files.append(f"📁 {dirname} - {description}")
            else:
                project_files.append(f"❌ {dirname} - {description}")
        
        files_panel = Panel.fit(
            "\n".join(project_files),
            title="📁 Project Structure",
            border_style="yellow"
        )
        console.print(files_panel)
        
        # Next steps suggestions
        suggestions = []
        
        if agents_count == 0:
            suggestions.append("• Add an agent: abi-core add agent --name YourAgent")
        
        if services_count == 0:
            suggestions.append("• Add semantic layer: abi-core add service semantic-layer")
            suggestions.append("• Add security: abi-core add service guardian")
        
        if policies_count == 0:
            suggestions.append("• Add policies: abi-core add policies --name YourPolicies")
        
        if not Path('compose.yaml').exists():
            suggestions.append("• Recreate project structure: abi-core create project")
        
        if suggestions:
            suggestions_panel = Panel.fit(
                "\n".join(suggestions),
                title="💡 Suggested Next Steps",
                border_style="cyan"
            )
            console.print(suggestions_panel)
        else:
            console.print("🎉 [green]Project is fully configured! Run with: abi-core run[/green]")
    
    else:
        console.print("❌ Project configuration not found", style="red")