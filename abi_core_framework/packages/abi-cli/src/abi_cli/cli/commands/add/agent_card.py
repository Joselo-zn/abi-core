"""
`add agent-card` — create/register a standalone agent card.
"""

import click
from pathlib import Path
from rich.prompt import Prompt

from ..utils import console, update_runtime_config
from .shared import _generate_agent_card
from .compose import _update_compose_with_agent_card


@click.command("agent-card")
@click.option('--name', '-n', required=True, help='Agent name')
@click.option('--description', '-d', help='Agent description')
@click.option('--model', default='llama3.2:3b', help='LLM model for the agent')
@click.option('--url', help='Agent URL (e.g., http://localhost:8000)')
@click.option('--tasks', help='Comma-separated list of supported tasks')
def add_agent_card(name, description, model, url, tasks):
    """Create an agent card for semantic layer registration"""

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    # Check if semantic layer service exists
    semantic_service_dir = None
    services_dir = Path('services')

    if services_dir.exists():
        for service_path in services_dir.iterdir():
            if service_path.is_dir():
                # Check for semantic layer structure (embedding_mesh directory)
                semantic_dir = service_path / 'embedding_mesh'
                if semantic_dir.exists():
                    semantic_service_dir = service_path
                    break

    if not semantic_service_dir:
        console.print("❌ No semantic layer service found. Run 'abi-core add service semantic-layer' first.", style="red")
        return

    # Get project name for Docker service URL
    runtime_file = Path('.abi/runtime.yaml')
    project_name = Path.cwd().name  # default
    if runtime_file.exists():
        try:
            import yaml
            with open(runtime_file, 'r') as f:
                runtime_data = yaml.safe_load(f)
                project_name = runtime_data.get('project', {}).get('name', Path.cwd().name)
        except Exception:
            pass

    project_dir = project_name.lower().replace(' ', '-').replace('_', '-')
    agent_name_normalized = name.lower().replace(' ', '_').replace('-', '_')

    # Interactive prompts if not provided
    if not description:
        description = Prompt.ask("Agent description", default=f"Specialized agent for {name}")

    if not url:
        # Default to Docker service name for inter-container communication
        default_url = f"http://{project_dir}-{agent_name_normalized}:8000"
        url = Prompt.ask("Agent URL", default=default_url)

    if not tasks:
        tasks = Prompt.ask("Supported tasks (comma-separated)", default="process_request,analyze_data")

    # Parse tasks
    task_list = [task.strip() for task in tasks.split(',') if task.strip()]

    # Generate agent card filename
    agent_card_filename = f"{name.lower().replace(' ', '_').replace('-', '_')}_agent.json"

    # Define target directories for agent cards
    semantic_agent_cards_dir = semantic_service_dir / 'agent_cards'
    semantic_agent_cards_dir.mkdir(parents=True, exist_ok=True)

    # Check if agent card already exists in semantic layer
    semantic_agent_card_path = semantic_agent_cards_dir / agent_card_filename
    if semantic_agent_card_path.exists():
        console.print(f"❌ Agent card '{agent_card_filename}' already exists in semantic layer", style="red")
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("Creating agent card...", total=None)

        # Generate agent card content
        agent_card = _generate_agent_card(name, description, model, url, task_list)

        # Write agent card to semantic layer
        progress.update(task, description="Writing agent card to semantic layer...")
        with open(semantic_agent_card_path, 'w') as f:
            import json
            json.dump(agent_card, f, indent=2)

        # Also create agent card in agent's directory if agent exists
        agent_name_normalized = name.lower().replace(' ', '_').replace('-', '_')
        agent_dir = Path('agents') / agent_name_normalized
        agent_card_locations = [str(semantic_agent_card_path)]

        if agent_dir.exists():
            progress.update(task, description="Writing agent card to agent directory...")
            agent_agent_cards_dir = agent_dir / 'agent_cards'
            agent_agent_cards_dir.mkdir(exist_ok=True)
            agent_agent_card_path = agent_agent_cards_dir / agent_card_filename

            with open(agent_agent_card_path, 'w') as f:
                json.dump(agent_card, f, indent=2)

            agent_card_locations.append(str(agent_agent_card_path))

        # Update runtime configuration
        update_runtime_config('agent_cards', {
            agent_name_normalized: {
                'name': name,
                'description': description,
                'model': model,
                'url': url,
                'tasks': task_list,
                'locations': agent_card_locations
            }
        })

        # Update docker-compose if agent exists
        if agent_dir.exists():
            progress.update(task, description="Updating docker-compose...")
            _update_compose_with_agent_card(agent_name_normalized, agent_card_filename)

        progress.update(task, description="Agent card created successfully!", completed=True)

    console.print(f"\n✅ Agent card '{name}' created successfully!", style="green")
    console.print(f"📁 Semantic layer: {semantic_agent_card_path}", style="blue")
    if len(agent_card_locations) > 1:
        console.print(f"📁 Agent directory: {agent_card_locations[1]}", style="blue")
    else:
        console.print("💡 Create an agent with the same name to also store the card in the agent directory", style="yellow")
    console.print(f"🔗 URL: {url}", style="cyan")
    console.print(f"📋 Tasks: {', '.join(task_list)}", style="yellow")
