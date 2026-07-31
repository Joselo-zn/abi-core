"""
`add agent` — scaffold a new agent (files, agent card, compose service).
"""

import click
from pathlib import Path
from rich.prompt import Prompt

from ..utils import console, update_runtime_config, render_template_content
from .shared import _generate_agent_card, _get_next_available_port
from .compose import _update_compose_with_agent, _update_compose_with_agent_card


@click.command("agent")
@click.option('--name', '-n', required=True, help='Agent name')
@click.option('--description', '-d', help='Agent description')
@click.option('--model', default='qwen2.5:3b', help='LLM model to use')
@click.option('--with-web-interface', is_flag=True, help='Include web interface for HTTP/SSE access')
def add_agent(name, description, model, with_web_interface):
    """Add a new agent to the project"""

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    # Read runtime.yaml to get project name
    runtime_file = Path('.abi/runtime.yaml')
    project_name = Path.cwd().name  # default
    if runtime_file.exists():
        try:
            import yaml
            with open(runtime_file, 'r') as f:
                runtime_data = yaml.safe_load(f)
                project_name = runtime_data.get('project', {}).get('name', Path.cwd().name)
        except Exception:
            pass  # Use default if can't read

    project_dir = project_name.lower().replace(' ', '-').replace('_', '-')

    if not description:
        description = Prompt.ask("Agent description", default=f"Specialized agent for {name}")

    agent_dir = Path('agents') / name.lower().replace(' ', '_').replace('-', '_')

    if agent_dir.exists():
        console.print(f"❌ Agent '{name}' already exists", style="red")
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("Creating agent...", total=None)

        # Create agent directory
        agent_dir.mkdir(parents=True)
        (agent_dir / '__init__.py').touch()

        # Create config directory
        config_dir = agent_dir / 'config'
        config_dir.mkdir(exist_ok=True)

        # Auto-assign ports
        agent_port = _get_next_available_port(8000)
        web_interface_port = _get_next_available_port(agent_port + 1) if with_web_interface else None

        # Template context
        agent_file_name = f'agent_{name.lower().replace(" ", "_").replace("-", "_")}'
        context = {
            'agent_name': name.lower().replace(' ', '_').replace('-', '_'),
            'agent_class_name': name.replace(' ', '').replace('-', '').replace('_', '') + 'Agent',
            'agent_description': description,
            'agent_display_name': name,
            'agent_file_name': agent_file_name,
            'model_name': model,
            'agent_port': agent_port,
            'with_web_interface': with_web_interface,
            'web_interface_port': web_interface_port,
            'project_name': project_name,
            'project_dir': project_dir,
            'tasks': [],  # populated after skills prompt below
        }

        # Generate config files
        with open(config_dir / '__init__.py', 'w') as f:
            f.write(render_template_content('agent/config/__init__.py', context))

        with open(config_dir / 'config.py', 'w') as f:
            f.write(render_template_content('agent/config/config.py', context))

        # Generate agent file using template
        with open(agent_dir / f'{agent_file_name}.py', 'w') as f:
            f.write(render_template_content('agent/agent.py', context))

        # Generate app.py (AbiCore instance — imported by tools, steps, tasks)
        with open(agent_dir / 'app.py', 'w') as f:
            f.write(render_template_content('agent/app.py', context))

        # NOTE: main.py, tools.py, steps.py, tasks.py are generated after
        # the skills prompt below so they can include task scaffolding

        # Generate models.py file
        with open(agent_dir / 'models.py', 'w') as f:
            f.write(render_template_content('agent/models.py', context))

        # Generate Dockerfile
        with open(agent_dir / 'Dockerfile', 'w') as f:
            f.write(render_template_content('agent/Dockerfile', context))

        # Generate requirements.txt
        with open(agent_dir / 'requirements.txt', 'w') as f:
            f.write(render_template_content('agent/requirements.txt', context))

        # Note: common utilities are now available from abi_core.common
        # No need to generate local common directory

        # Generate web interface if requested
        if with_web_interface:
            with open(agent_dir / 'web_interface.py', 'w') as f:
                f.write(render_template_content('common/web_interface', context))

        # Update runtime configuration
        update_runtime_config('agents', {
            name.lower().replace(' ', '_').replace('-', '_'): {
                'name': name,
                'description': description,
                'model': model,
                'port': agent_port,
                'web_interface_port': web_interface_port,
                'path': str(agent_dir)
            }
        })

        # Update docker-compose.yml
        _update_compose_with_agent(context)

        progress.update(task, description="Agent created successfully!", completed=True)

    # ── Skills / Agent Card interactive session ─────────────────
    console.print(f"\n✅ Agent '{name}' created!", style="green")
    console.print(f"📁 Location: {agent_dir}", style="blue")
    console.print(f"🚀 Port: {agent_port}", style="cyan")

    if with_web_interface:
        console.print(f"🌐 Web interface enabled on port {web_interface_port}", style="cyan")
        console.print(f"   Endpoints:", style="cyan")
        console.print(f"   - POST /stream - SSE streaming", style="cyan")
        console.print(f"   - POST /query - Single query", style="cyan")
        console.print(f"   - GET /health - Health check", style="cyan")

    console.print(f"\n🎯 Now let's define the agent's skills and create its agent card.", style="cyan")

    # Prompt for tasks/skills
    tasks_input = Prompt.ask(
        "Supported tasks/skills (comma-separated)",
        default="process_request,analyze_data"
    )
    raw_task_list = [t.strip() for t in tasks_input.split(',') if t.strip()]

    # Task names become Python function names in steps.py/tasks.py, so they must
    # be valid identifiers. Sanitize spaces/hyphens/etc. (e.g. "chat with user"
    # → "chat_with_user"). The agent card keeps its own sanitization separately.
    task_list = [_sanitize_task_name(t) for t in raw_task_list]

    # Now generate main.py, tools.py, steps.py, tasks.py with task scaffolding
    context['tasks'] = task_list
    with open(agent_dir / 'main.py', 'w') as f:
        f.write(render_template_content('agent/main.py', context))
    with open(agent_dir / 'tools.py', 'w') as f:
        f.write(render_template_content('agent/tools.py', context))
    with open(agent_dir / 'steps.py', 'w') as f:
        f.write(render_template_content('agent/steps.py', context))
    with open(agent_dir / 'tasks.py', 'w') as f:
        f.write(render_template_content('agent/tasks.py', context))

    # Build agent URL for Docker inter-container communication
    agent_name_normalized = name.lower().replace(' ', '_').replace('-', '_')
    default_url = f"http://{project_dir}-{agent_name_normalized}:{agent_port}"
    agent_url = Prompt.ask("Agent URL", default=default_url)

    # Generate agent card
    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Creating agent card...", total=None)

        agent_card = _generate_agent_card(name, description, model, agent_url, task_list)
        agent_card_filename = f"{agent_name_normalized}_agent.json"

        # Save agent card in agent directory
        agent_cards_dir = agent_dir / 'agent_cards'
        agent_cards_dir.mkdir(exist_ok=True)

        import json
        agent_card_path = agent_cards_dir / agent_card_filename
        with open(agent_card_path, 'w') as f:
            json.dump(agent_card, f, indent=2)

        agent_card_locations = [str(agent_card_path)]

        # Copy to semantic layer if it exists
        progress.update(task, description="Checking semantic layer...")
        semantic_service_dir = None
        services_dir = Path('services')
        if services_dir.exists():
            for service_path in services_dir.iterdir():
                if service_path.is_dir():
                    semantic_dir = service_path / 'embedding_mesh'
                    if semantic_dir.exists():
                        semantic_service_dir = service_path
                        break

        if semantic_service_dir:
            progress.update(task, description="Copying agent card to semantic layer...")
            semantic_agent_cards_dir = semantic_service_dir / 'agent_cards'
            semantic_agent_cards_dir.mkdir(parents=True, exist_ok=True)
            semantic_card_path = semantic_agent_cards_dir / agent_card_filename
            with open(semantic_card_path, 'w') as f:
                json.dump(agent_card, f, indent=2)
            agent_card_locations.append(str(semantic_card_path))

        # Register agent card in runtime config
        progress.update(task, description="Updating runtime configuration...")
        update_runtime_config('agent_cards', {
            agent_name_normalized: {
                'name': name,
                'description': description,
                'model': model,
                'url': agent_url,
                'tasks': task_list,
                'locations': agent_card_locations
            }
        })

        # Update docker-compose with AGENT_CARD env var
        _update_compose_with_agent_card(agent_name_normalized, agent_card_filename)

        progress.update(task, description="Agent card created!", completed=True)

    console.print(f"\n🃏 Agent card created:", style="green")
    console.print(f"   📁 Agent: {agent_card_path}", style="blue")
    if semantic_service_dir:
        console.print(f"   📁 Semantic layer: {semantic_card_path}", style="blue")
    else:
        console.print(f"   💡 Add a semantic layer to enable agent discovery: abi-core add semantic-layer", style="yellow")
    console.print(f"   🎯 Skills: {', '.join(task_list)}", style="cyan")
    console.print(f"\n📦 Docker service added to compose file", style="green")
    console.print(f"   Run: docker-compose up {context['agent_name']}-agent", style="blue")


def _sanitize_task_name(name: str) -> str:
    """Turn a free-text task name into a valid Python identifier.

    Task names are used as function names in the generated steps.py/tasks.py
    (``async def {name}(...)``), so "chat with user" or "answer-questions" must
    become "chat_with_user" / "answer_questions". Falls back to a safe default
    if the input has no usable characters or starts with a digit.
    """
    import re

    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower()).strip("_")
    if not slug:
        return "task"
    if slug[0].isdigit():
        slug = f"task_{slug}"
    return slug
