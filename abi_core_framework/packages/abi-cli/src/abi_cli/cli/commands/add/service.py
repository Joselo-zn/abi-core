"""
`add service` / `add semantic-layer` — scaffold semantic-layer, guardian,
guardian-native, and mcp-api services.
"""

import click
from pathlib import Path
from rich.prompt import Prompt

from ..utils import console, update_runtime_config, render_template_content
from .compose import _update_compose_with_service, _update_compose_with_semantic_layer


@click.command("service")
@click.argument('service_type', type=click.Choice(['semantic-layer', 'guardian', 'guardian-native', 'mcp-api']))
@click.option('--name', '-n', help='Service name (optional, not used for semantic-layer)')
@click.option('--domain', help='Domain specialization')
def add_service(service_type, name, domain):
    """Add a service to the project

    SERVICE_TYPE options:

    \b
    semantic-layer    Add AI agent discovery and routing service (uses fixed name 'semantic_layer')
    guardian          Add security policy enforcement service (placeholder)
    guardian-native   Add native guardian service based on abi-core guardial
    mcp-api          Add FastMCP/API central connection point service

    Note: You can also use 'abi-core add semantic-layer' as a shortcut.
    """

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    # Handle semantic-layer special case - always use 'semantic_layer' as name
    if service_type == 'semantic-layer':
        name = 'semantic_layer'
        service_dir = Path('services') / 'semantic_layer'
    else:
        if not name:
            name = Prompt.ask(f"Service name", default=f"{service_type.replace('-', '_')}_service")
        service_dir = Path('services') / name.lower().replace(' ', '_').replace('-', '_')

    if not domain:
        domain = Prompt.ask("Domain specialization", default="general")

    # Special check for semantic-layer - also check for existing semantic layer services
    if service_type == 'semantic-layer':
        if service_dir.exists():
            console.print("❌ Semantic layer service already exists!", style="red")
            console.print(f"📁 Location: {service_dir}", style="blue")
            console.print("💡 Use 'abi-core remove service semantic_layer' to remove it first if you want to recreate it.", style="yellow")
            return

        # Check if there's any other semantic layer service with different name
        services_dir = Path('services')
        if services_dir.exists():
            for service_path in services_dir.iterdir():
                if service_path.is_dir() and service_path != service_dir:
                    # Check if it has semantic layer structure (embedding_mesh directory)
                    if (service_path / 'embedding_mesh').exists():
                        console.print(f"❌ Semantic layer service already exists with name '{service_path.name}'!", style="red")
                        console.print(f"📁 Location: {service_path}", style="blue")
                        return
    else:
        # Regular check for other service types
        if service_dir.exists():
            console.print(f"❌ Service '{name}' already exists", style="red")
            return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task(f"Creating {service_type} service...", total=None)

        # Create service directory
        service_dir.mkdir(parents=True)
        (service_dir / '__init__.py').touch()

        if service_type == 'semantic-layer':
            _create_semantic_layer_service(service_dir, domain)

        elif service_type == 'guardian':
            # Create guardian placeholder structure
            (service_dir / 'guard_core').mkdir()
            (service_dir / 'guard_core' / '__init__.py').touch()

        elif service_type == 'guardian-native':
            _create_guardian_native_service(service_dir, name, domain)

        elif service_type == 'mcp-api':
            _create_mcp_api_service(service_dir, name, domain)

        # Determine default port based on service type
        default_port = {
            'semantic-layer': 10100,
            'guardian': 11438,
            'guardian-native': 11439,
            'mcp-api': 9000
        }.get(service_type, 8080)

        # Update runtime configuration
        update_runtime_config('services', {
            name.lower().replace(' ', '_').replace('-', '_'): {
                'name': name,
                'type': service_type,
                'domain': domain,
                'port': default_port,
                'path': str(service_dir)
            }
        })

        # Update docker-compose.yml if it exists
        compose_file = Path('compose.yaml')
        if not compose_file.exists():
            compose_file = Path('docker-compose.yml')

        if compose_file.exists():
            progress.update(task, description="Updating Docker Compose...")
            context = {
                'service_name': name,
                'service_type': service_type,
                'domain': domain,
                'project_name': Path.cwd().name
            }
            _update_compose_with_service(compose_file, name, service_type, default_port, context)

        progress.update(task, description="Service created successfully!", completed=True)

    console.print(f"\n✅ Service '{name}' added successfully!", style="green")
    console.print(f"📁 Location: {service_dir}", style="blue")
    console.print(f"🌐 Default port: {default_port}", style="blue")
    console.print(f"🏷️  Domain: {domain}", style="blue")
    console.print("\n📋 Next steps:", style="yellow")
    console.print("  1. Run 'abi-core run' to start all services", style="dim")
    console.print(f"  2. The service will be available at http://localhost:{default_port}", style="dim")


@click.command("semantic-layer")
@click.option('--domain', help='Domain specialization', default='general')
def add_semantic_layer(domain):
    """Add semantic layer service to the project

    The semantic layer provides:
    - AI agent discovery and routing via MCP server
    - Semantic search with embeddings
    - Access validation with OPA policies
    - Agent card management

    This is equivalent to 'abi-core add service semantic-layer'.
    """

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    # Check if semantic layer already exists
    services_dir = Path('services')
    semantic_layer_dir = services_dir / 'semantic_layer'

    if semantic_layer_dir.exists():
        console.print("❌ Semantic layer service already exists!", style="red")
        console.print(f"📁 Location: {semantic_layer_dir}", style="blue")
        console.print("💡 Use 'abi-core remove service semantic_layer' to remove it first if you want to recreate it.", style="yellow")
        return

    # Check if there's any other semantic layer service with different name
    if services_dir.exists():
        for service_path in services_dir.iterdir():
            if service_path.is_dir():
                # Check if it has semantic layer structure (embedding_mesh directory)
                if (service_path / 'embedding_mesh').exists():
                    console.print(f"❌ Semantic layer service already exists with name '{service_path.name}'!", style="red")
                    console.print(f"📁 Location: {service_path}", style="blue")
                    return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("Creating semantic layer service...", total=None)

        # Create services directory if it doesn't exist
        services_dir.mkdir(exist_ok=True)

        # Create semantic layer directory
        semantic_layer_dir.mkdir()

        # Get project name from current directory
        project_name = Path.cwd().name

        # Create context for templates
        context = {
            'project_name': project_name,
            'domain': domain,
            'service_name': 'semantic_layer'
        }

        # Generate complete semantic layer structure
        progress.update(task, description="Generating semantic layer files...")
        from ..create import _create_semantic_layer_structure
        _create_semantic_layer_structure(semantic_layer_dir, context)

        # Update runtime configuration
        progress.update(task, description="Updating configuration...")
        update_runtime_config('services', {
            'semantic_layer': {
                'name': 'Semantic Layer',
                'type': 'semantic-layer',
                'domain': domain,
                'port': 10100,
                'path': str(semantic_layer_dir),
                'enabled': True
            }
        })

        # Update docker-compose.yml if it exists
        compose_file = Path('compose.yaml')
        if compose_file.exists():
            progress.update(task, description="Updating Docker Compose...")
            _update_compose_with_semantic_layer(compose_file, context)

        progress.update(task, description="Semantic layer created successfully!", completed=True)

    console.print(f"\n✅ Semantic layer service added successfully!", style="green")
    console.print(f"📁 Location: {semantic_layer_dir}", style="blue")
    console.print(f"🌐 Port: 10100", style="blue")
    console.print(f"🏷️  Domain: {domain}", style="blue")
    console.print("\n📋 Next steps:", style="yellow")
    console.print("  1. Run 'abi-core run' to start all services", style="dim")
    console.print("  2. The semantic layer will be available at http://localhost:10100", style="dim")
    console.print("  3. Add agent cards to enable semantic search", style="dim")


def _create_semantic_layer_service(service_dir, domain):
    """Create semantic layer service structure"""
    # Import the helper function from create.py
    from ..create import _create_semantic_layer_structure

    context = {'domain': domain or 'general', 'project_name': service_dir.parent.parent.name}
    _create_semantic_layer_structure(service_dir, context)


def _create_guardian_native_service(service_dir, name, domain):
    """Create native guardian service using templates"""
    console.print("🛡️ Creating native Guardian service...", style="blue")

    # Create structure
    (service_dir / 'agent').mkdir()
    (service_dir / 'agent' / 'models').mkdir()
    (service_dir / 'opa' / 'policies').mkdir(parents=True)
    (service_dir / 'config').mkdir()

    # Context for templates
    context = {
        'project_name': Path.cwd().name,
        'service_name': name or 'guardian',
        'domain': domain or 'general'
    }

    # Guardian config files (inside agent/)
    guardian_config_files = [
        ('agent/config/__init__.py', 'service_guardian/agent/config/__init__.py'),
        ('agent/config/config.py', 'service_guardian/agent/config/config.py'),
    ]

    # Guardian agent files
    guardian_files = [
        ('agent/__init__.py', 'service_guardian/agent/__init__.py'),
        ('agent/guardial_secure.py', 'service_guardian/agent/guardial_secure.py'),
        ('agent/emergency_response.py', 'service_guardian/agent/emergency_response.py'),
        ('agent/dashboard.py', 'service_guardian/agent/dashboard.py'),
        ('agent/alerting_system.py', 'service_guardian/agent/alerting_system.py'),
        ('agent/metrics_collector.py', 'service_guardian/agent/metrics_collector.py'),
        ('agent/audit_persistence.py', 'service_guardian/agent/audit_persistence.py'),
        ('agent/policy_engine_secure.py', 'service_guardian/agent/policy_engine_secure.py'),
        ('agent/mcp_interface.py', 'service_guardian/agent/mcp_interface.py'),
        ('agent/main.py', 'service_guardian/agent/main.py'),
        ('agent/models/agent_models.py', 'service_guardian/agent/models/agent_models.py'),
    ]

    # Root level files
    root_files = [
        ('Dockerfile', 'service_guardian/Dockerfile'),
        ('requirements.txt', 'service_guardian/requirements.txt'),
        ('README.md', 'service_guardian/README.md'),
        ('alerting_config.json', 'service_guardian/alerting_config.json'),
    ]

    # OPA files
    opa_files = [
        ('opa/policies/semantic_access.rego', 'service_guardian/opa/policies/semantic_access.rego'),
        ('opa/policies/a2a_access.rego', 'service_guardian/opa/policies/a2a_access.rego'),
        ('opa/policies/basic.rego', 'service_guardian/opa/policies/basic.rego'),
    ]

    # Create all files
    all_files = guardian_config_files + guardian_files + root_files + opa_files

    for file_path, template_path in all_files:
        full_path = service_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, 'w') as f:
                f.write(render_template_content(template_path, context))
        except Exception as e:
            console.print(f"⚠️ Could not create {file_path}: {e}", style="yellow")

    console.print("✅ Native Guardian service created successfully", style="green")


def _create_mcp_api_service(service_dir, name, domain):
    """Create MCP API service structure"""
    console.print("🔌 Creating MCP API service...", style="blue")

    # Create main.py
    context = {
        'project_name': Path.cwd().name,
        'service_name': name,
        'domain': domain
    }

    with open(service_dir / 'main.py', 'w') as f:
        f.write(render_template_content('service_mcp_api/main.py', context))

    # Create requirements.txt
    with open(service_dir / 'requirements.txt', 'w') as f:
        f.write(render_template_content('service_mcp_api/requirements.txt', context))

    # Create Dockerfile
    with open(service_dir / 'Dockerfile', 'w') as f:
        f.write(render_template_content('service_mcp_api/Dockerfile', context))

    console.print("✅ MCP API service created successfully", style="green")
