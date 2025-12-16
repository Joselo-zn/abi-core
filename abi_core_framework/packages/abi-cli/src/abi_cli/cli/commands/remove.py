"""
Remove commands for ABI Core CLI
"""

import click
import shutil
import yaml
from pathlib import Path
from rich.prompt import Confirm
from rich.panel import Panel
from rich.table import Table

from .utils import console


@click.group()
def remove():
    """Remove components from ABI project"""
    pass


@remove.command("agent")
@click.argument('agent_name')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without doing it')
@click.option('--keep-compose', is_flag=True, help='Do not modify compose.yaml')
@click.option('--keep-runtime', is_flag=True, help='Do not modify runtime.yaml')
def remove_agent(agent_name, force, dry_run, keep_compose, keep_runtime):
    """Remove an agent from the project
    
    \b
    Examples:
      abi-core remove agent sales
      abi-core remove agent sales --force
      abi-core remove agent sales --dry-run
    """
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        return
    
    # Normalize agent name
    agent_name_normalized = agent_name.lower().replace(' ', '_').replace('-', '_')
    agent_dir = Path('agents') / agent_name_normalized
    
    # Check if agent exists
    if not agent_dir.exists():
        console.print(f"❌ Agent '{agent_name}' not found at {agent_dir}", style="red")
        return
    
    # Load runtime.yaml
    runtime_file = Path('.abi/runtime.yaml')
    runtime_config = {}
    if runtime_file.exists():
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
    
    # Get project name
    project_name = runtime_config.get('project', {}).get('name', Path.cwd().name)
    project_dir = project_name.lower().replace(' ', '_').replace('-', '_')
    
    # Collect what will be removed
    items_to_remove = []
    items_to_remove.append(f"Agent directory: {agent_dir}")
    
    # Check for agent cards
    agent_card_locations = []
    if runtime_config.get('agent_cards', {}).get(agent_name_normalized):
        locations = runtime_config['agent_cards'][agent_name_normalized].get('locations', [])
        for loc in locations:
            loc_path = Path(loc)
            if loc_path.exists():
                agent_card_locations.append(loc_path)
                items_to_remove.append(f"Agent card: {loc}")
    
    # Check compose service
    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')
    
    service_name = None
    if compose_file.exists() and not keep_compose:
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}
        
        # Try different service name patterns
        possible_names = [
            f"{project_dir}-{agent_name_normalized}",
            f"{agent_name_normalized}-agent",
            agent_name_normalized
        ]
        
        for name in possible_names:
            if name in compose_data.get('services', {}):
                service_name = name
                items_to_remove.append(f"Docker service: {service_name}")
                break
    
    # Check runtime.yaml entries
    if not keep_runtime:
        if agent_name_normalized in runtime_config.get('agents', {}):
            items_to_remove.append(f"Runtime config: agents.{agent_name_normalized}")
        if agent_name_normalized in runtime_config.get('agent_cards', {}):
            items_to_remove.append(f"Runtime config: agent_cards.{agent_name_normalized}")
    
    # Display what will be removed
    console.print(f"\n🗑️  Removing agent '{agent_name}'...", style="cyan bold")
    console.print("=" * 60, style="cyan")
    
    if dry_run:
        console.print("\n[DRY RUN] The following would be removed:\n", style="yellow bold")
    else:
        console.print("\n⚠️  This will remove:\n", style="yellow bold")
    
    for item in items_to_remove:
        console.print(f"  • {item}", style="yellow")
    
    if dry_run:
        console.print("\n✅ Dry run complete. No changes made.", style="green")
        return
    
    # Ask for confirmation
    if not force:
        console.print()
        if not Confirm.ask("❓ Are you sure?", default=False):
            console.print("❌ Operation cancelled.", style="yellow")
            return
    
    # Perform removal
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Remove agent directory
        task = progress.add_task(f"[1/{len(items_to_remove)}] Removing agent directory...", total=None)
        try:
            shutil.rmtree(agent_dir)
            progress.update(task, description=f"✅ Agent directory removed")
        except Exception as e:
            progress.update(task, description=f"❌ Error removing directory: {e}")
        
        # Remove agent cards
        if agent_card_locations:
            task = progress.add_task(f"[2/{len(items_to_remove)}] Removing agent cards...", total=None)
            for card_path in agent_card_locations:
                try:
                    card_path.unlink()
                except Exception as e:
                    console.print(f"⚠️  Could not remove {card_path}: {e}", style="yellow")
            progress.update(task, description=f"✅ Agent cards removed")
        
        # Update compose.yaml
        if service_name and not keep_compose:
            task = progress.add_task(f"[3/{len(items_to_remove)}] Updating compose.yaml...", total=None)
            try:
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f) or {}
                
                if service_name in compose_data.get('services', {}):
                    del compose_data['services'][service_name]
                
                with open(compose_file, 'w') as f:
                    yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
                
                progress.update(task, description=f"✅ compose.yaml updated")
            except Exception as e:
                progress.update(task, description=f"⚠️  Error updating compose: {e}")
        
        # Update runtime.yaml
        if not keep_runtime:
            task = progress.add_task(f"[4/{len(items_to_remove)}] Updating runtime.yaml...", total=None)
            try:
                if agent_name_normalized in runtime_config.get('agents', {}):
                    del runtime_config['agents'][agent_name_normalized]
                
                if agent_name_normalized in runtime_config.get('agent_cards', {}):
                    del runtime_config['agent_cards'][agent_name_normalized]
                
                with open(runtime_file, 'w') as f:
                    yaml.dump(runtime_config, f, default_flow_style=False, sort_keys=False)
                
                progress.update(task, description=f"✅ runtime.yaml updated")
            except Exception as e:
                progress.update(task, description=f"⚠️  Error updating runtime: {e}")
    
    # Success message
    console.print("\n" + "=" * 60, style="green")
    console.print(f"✅ Agent '{agent_name}' removed successfully!", style="green bold")
    console.print("=" * 60, style="green")
    
    if service_name:
        console.print("\n💡 Next steps:", style="cyan")
        console.print(f"  • Stop the container: docker-compose down {service_name}", style="dim")
        console.print(f"  • Restart other services: docker-compose up -d", style="dim")


@remove.command("service")
@click.argument('service_name')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without doing it')
def remove_service(service_name, force, dry_run):
    """Remove a service from the project
    
    \b
    Examples:
      abi-core remove service guardian
      abi-core remove service semantic_layer --force
    """
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        return
    
    # Normalize service name
    service_name_normalized = service_name.lower().replace(' ', '_').replace('-', '_')
    service_dir = Path('services') / service_name_normalized
    
    # Check if service exists
    if not service_dir.exists():
        console.print(f"❌ Service '{service_name}' not found at {service_dir}", style="red")
        return
    
    # Load runtime.yaml
    runtime_file = Path('.abi/runtime.yaml')
    runtime_config = {}
    if runtime_file.exists():
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
    
    # Check if it's semantic layer with active agents
    service_info = runtime_config.get('services', {}).get(service_name_normalized, {})
    if service_info.get('type') == 'semantic-layer':
        agents = runtime_config.get('agents', {})
        if agents:
            console.print("❌ Cannot remove semantic layer while agents exist!", style="red")
            console.print(f"   Active agents: {', '.join(agents.keys())}", style="yellow")
            console.print("💡 Remove agents first, then remove semantic layer.", style="cyan")
            return
    
    # Get project name
    project_name = runtime_config.get('project', {}).get('name', Path.cwd().name)
    project_dir = project_name.lower().replace(' ', '_').replace('-', '_')
    
    # Collect what will be removed
    items_to_remove = []
    items_to_remove.append(f"Service directory: {service_dir}")
    
    # Check compose service
    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')
    
    compose_service_name = None
    if compose_file.exists():
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}
        
        # Try different service name patterns
        possible_names = [
            f"{project_dir}-{service_name_normalized}",
            service_name_normalized
        ]
        
        for name in possible_names:
            if name in compose_data.get('services', {}):
                compose_service_name = name
                items_to_remove.append(f"Docker service: {compose_service_name}")
                break
    
    # Check runtime.yaml entry
    if service_name_normalized in runtime_config.get('services', {}):
        items_to_remove.append(f"Runtime config: services.{service_name_normalized}")
    
    # Display what will be removed
    console.print(f"\n🗑️  Removing service '{service_name}'...", style="cyan bold")
    console.print("=" * 60, style="cyan")
    
    if dry_run:
        console.print("\n[DRY RUN] The following would be removed:\n", style="yellow bold")
    else:
        console.print("\n⚠️  This will remove:\n", style="yellow bold")
    
    for item in items_to_remove:
        console.print(f"  • {item}", style="yellow")
    
    if dry_run:
        console.print("\n✅ Dry run complete. No changes made.", style="green")
        return
    
    # Ask for confirmation
    if not force:
        console.print()
        if not Confirm.ask("❓ Are you sure?", default=False):
            console.print("❌ Operation cancelled.", style="yellow")
            return
    
    # Perform removal
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Remove service directory
        task = progress.add_task("[1/3] Removing service directory...", total=None)
        try:
            shutil.rmtree(service_dir)
            progress.update(task, description="✅ Service directory removed")
        except Exception as e:
            progress.update(task, description=f"❌ Error removing directory: {e}")
        
        # Update compose.yaml
        if compose_service_name:
            task = progress.add_task("[2/3] Updating compose.yaml...", total=None)
            try:
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f) or {}
                
                if compose_service_name in compose_data.get('services', {}):
                    del compose_data['services'][compose_service_name]
                
                with open(compose_file, 'w') as f:
                    yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
                
                progress.update(task, description="✅ compose.yaml updated")
            except Exception as e:
                progress.update(task, description=f"⚠️  Error updating compose: {e}")
        
        # Update runtime.yaml
        task = progress.add_task("[3/3] Updating runtime.yaml...", total=None)
        try:
            if service_name_normalized in runtime_config.get('services', {}):
                del runtime_config['services'][service_name_normalized]
            
            with open(runtime_file, 'w') as f:
                yaml.dump(runtime_config, f, default_flow_style=False, sort_keys=False)
            
            progress.update(task, description="✅ runtime.yaml updated")
        except Exception as e:
            progress.update(task, description=f"⚠️  Error updating runtime: {e}")
    
    # Success message
    console.print("\n" + "=" * 60, style="green")
    console.print(f"✅ Service '{service_name}' removed successfully!", style="green bold")
    console.print("=" * 60, style="green")
    
    if compose_service_name:
        console.print("\n💡 Next steps:", style="cyan")
        console.print(f"  • Stop the container: docker-compose down {compose_service_name}", style="dim")
        console.print(f"  • Restart other services: docker-compose up -d", style="dim")


@remove.command("agentic-orchestration-layer")
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without doing it')
def remove_orchestration(force, dry_run):
    """Remove planner and orchestrator agents
    
    This removes both the Planner and Orchestrator agents that make up
    the agentic orchestration layer.
    
    \b
    Examples:
      abi-core remove agentic-orchestration-layer
      abi-core remove agentic-orchestration-layer --force
    """
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        return
    
    console.print("\n🗑️  Removing Agentic Orchestration Layer...", style="cyan bold")
    console.print("=" * 60, style="cyan")
    
    # Check if agents exist
    planner_dir = Path('agents/planner')
    orchestrator_dir = Path('agents/orchestrator')
    
    if not planner_dir.exists() and not orchestrator_dir.exists():
        console.print("❌ Agentic orchestration layer not found.", style="red")
        console.print("   Neither planner nor orchestrator agents exist.", style="yellow")
        return
    
    # Collect what will be removed
    items_to_remove = []
    
    if planner_dir.exists():
        items_to_remove.append("Planner agent directory: agents/planner")
    if orchestrator_dir.exists():
        items_to_remove.append("Orchestrator agent directory: agents/orchestrator")
    
    # Load runtime.yaml
    runtime_file = Path('.abi/runtime.yaml')
    runtime_config = {}
    if runtime_file.exists():
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
    
    # Get project name
    project_name = runtime_config.get('project', {}).get('name', Path.cwd().name)
    project_dir = project_name.lower().replace(' ', '_').replace('-', '_')
    
    # Check for agent cards
    for agent_name in ['planner', 'orchestrator']:
        if runtime_config.get('agent_cards', {}).get(agent_name):
            locations = runtime_config['agent_cards'][agent_name].get('locations', [])
            for loc in locations:
                if Path(loc).exists():
                    items_to_remove.append(f"Agent card: {loc}")
    
    # Check compose services
    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')
    
    compose_services = []
    if compose_file.exists():
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}
        
        for agent in ['planner', 'orchestrator']:
            service_name = f"{project_dir}-{agent}"
            if service_name in compose_data.get('services', {}):
                compose_services.append(service_name)
                items_to_remove.append(f"Docker service: {service_name}")
    
    # Display what will be removed
    if dry_run:
        console.print("\n[DRY RUN] The following would be removed:\n", style="yellow bold")
    else:
        console.print("\n⚠️  This will remove:\n", style="yellow bold")
    
    for item in items_to_remove:
        console.print(f"  • {item}", style="yellow")
    
    if dry_run:
        console.print("\n✅ Dry run complete. No changes made.", style="green")
        return
    
    # Ask for confirmation
    if not force:
        console.print()
        if not Confirm.ask("❓ Are you sure?", default=False):
            console.print("❌ Operation cancelled.", style="yellow")
            return
    
    # Perform removal
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Remove agent directories
        task = progress.add_task("[1/4] Removing agent directories...", total=None)
        try:
            if planner_dir.exists():
                shutil.rmtree(planner_dir)
            if orchestrator_dir.exists():
                shutil.rmtree(orchestrator_dir)
            progress.update(task, description="✅ Agent directories removed")
        except Exception as e:
            progress.update(task, description=f"❌ Error removing directories: {e}")
        
        # Remove agent cards
        task = progress.add_task("[2/4] Removing agent cards...", total=None)
        for agent_name in ['planner', 'orchestrator']:
            if runtime_config.get('agent_cards', {}).get(agent_name):
                locations = runtime_config['agent_cards'][agent_name].get('locations', [])
                for loc in locations:
                    try:
                        Path(loc).unlink(missing_ok=True)
                    except Exception as e:
                        console.print(f"⚠️  Could not remove {loc}: {e}", style="yellow")
        progress.update(task, description="✅ Agent cards removed")
        
        # Update compose.yaml
        if compose_services:
            task = progress.add_task("[3/4] Updating compose.yaml...", total=None)
            try:
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f) or {}
                
                for service_name in compose_services:
                    if service_name in compose_data.get('services', {}):
                        del compose_data['services'][service_name]
                
                # Remove volumes if they exist
                if 'volumes' in compose_data:
                    for vol in ['ollama-planner', 'ollama-orchestrator']:
                        if vol in compose_data['volumes']:
                            del compose_data['volumes'][vol]
                
                with open(compose_file, 'w') as f:
                    yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
                
                progress.update(task, description="✅ compose.yaml updated")
            except Exception as e:
                progress.update(task, description=f"⚠️  Error updating compose: {e}")
        
        # Update runtime.yaml
        task = progress.add_task("[4/4] Updating runtime.yaml...", total=None)
        try:
            for agent_name in ['planner', 'orchestrator']:
                if agent_name in runtime_config.get('agents', {}):
                    del runtime_config['agents'][agent_name]
                if agent_name in runtime_config.get('agent_cards', {}):
                    del runtime_config['agent_cards'][agent_name]
            
            with open(runtime_file, 'w') as f:
                yaml.dump(runtime_config, f, default_flow_style=False, sort_keys=False)
            
            progress.update(task, description="✅ runtime.yaml updated")
        except Exception as e:
            progress.update(task, description=f"⚠️  Error updating runtime: {e}")
    
    # Success message
    console.print("\n" + "=" * 60, style="green")
    console.print("✅ Agentic Orchestration Layer removed successfully!", style="green bold")
    console.print("=" * 60, style="green")
    
    if compose_services:
        console.print("\n💡 Next steps:", style="cyan")
        console.print(f"  • Stop containers: docker-compose down {' '.join(compose_services)}", style="dim")
        console.print(f"  • Restart other services: docker-compose up -d", style="dim")


@remove.command("agent-card")
@click.argument('agent_name')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
def remove_agent_card(agent_name, force):
    """Remove an agent card from semantic layer
    
    This removes only the agent card, not the agent itself.
    Useful for regenerating agent cards.
    
    \b
    Examples:
      abi-core remove agent-card sales
      abi-core remove agent-card planner --force
    """
    
    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        return
    
    # Normalize agent name
    agent_name_normalized = agent_name.lower().replace(' ', '_').replace('-', '_')
    
    # Load runtime.yaml
    runtime_file = Path('.abi/runtime.yaml')
    runtime_config = {}
    if runtime_file.exists():
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
    
    # Check if agent card exists
    if agent_name_normalized not in runtime_config.get('agent_cards', {}):
        console.print(f"❌ Agent card '{agent_name}' not found in runtime.yaml", style="red")
        return
    
    # Get agent card locations
    locations = runtime_config['agent_cards'][agent_name_normalized].get('locations', [])
    existing_locations = [Path(loc) for loc in locations if Path(loc).exists()]
    
    if not existing_locations:
        console.print(f"❌ No agent card files found for '{agent_name}'", style="red")
        return
    
    # Display what will be removed
    console.print(f"\n🗑️  Removing agent card '{agent_name}'...", style="cyan bold")
    console.print("=" * 60, style="cyan")
    console.print("\n⚠️  This will remove:\n", style="yellow bold")
    
    for loc in existing_locations:
        console.print(f"  • Agent card: {loc}", style="yellow")
    console.print(f"  • Runtime config: agent_cards.{agent_name_normalized}", style="yellow")
    
    # Ask for confirmation
    if not force:
        console.print()
        if not Confirm.ask("❓ Are you sure?", default=False):
            console.print("❌ Operation cancelled.", style="yellow")
            return
    
    # Perform removal
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Remove agent card files
        task = progress.add_task("[1/2] Removing agent card files...", total=None)
        for loc in existing_locations:
            try:
                loc.unlink()
            except Exception as e:
                console.print(f"⚠️  Could not remove {loc}: {e}", style="yellow")
        progress.update(task, description="✅ Agent card files removed")
        
        # Update runtime.yaml
        task = progress.add_task("[2/2] Updating runtime.yaml...", total=None)
        try:
            if agent_name_normalized in runtime_config.get('agent_cards', {}):
                del runtime_config['agent_cards'][agent_name_normalized]
            
            with open(runtime_file, 'w') as f:
                yaml.dump(runtime_config, f, default_flow_style=False, sort_keys=False)
            
            progress.update(task, description="✅ runtime.yaml updated")
        except Exception as e:
            progress.update(task, description=f"⚠️  Error updating runtime: {e}")
    
    # Success message
    console.print("\n" + "=" * 60, style="green")
    console.print(f"✅ Agent card '{agent_name}' removed successfully!", style="green bold")
    console.print("=" * 60, style="green")
    
    console.print("\n💡 The agent itself still exists.", style="cyan")
    console.print("   To regenerate the card, run: abi-core add agent-card", style="dim")
