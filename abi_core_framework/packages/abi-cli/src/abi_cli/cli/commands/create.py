"""
Create commands for ABI Core CLI
"""

import click
from pathlib import Path
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

from .utils import console, render_template_content


def _create_semantic_layer_structure(semantic_dir, context):
    """Create complete semantic layer structure with all templates"""
    
    # Create directory structure
    embedding_mesh_dir = semantic_dir / 'embedding_mesh'
    embedding_mesh_dir.mkdir(exist_ok=True)

    models_dir = embedding_mesh_dir / 'models'
    models_dir.mkdir(exist_ok=True)

    agent_cards_dir = semantic_dir / 'agent_cards'
    agent_cards_dir.mkdir(exist_ok=True)

    config_dir = semantic_dir / 'config'
    config_dir.mkdir(exist_ok=True)
    
    # Root level files
    files_to_create = [
        ('__init__.py', 'service_semantic_layer/__init__.py'),
        ('main.py', 'service_semantic_layer/main.py'),
        ('requirements.txt', 'service_semantic_layer/requirements.txt'),
        ('Dockerfile', 'service_semantic_layer/Dockerfile'),
    ]
    
    # Config files
    config_files = [
        ('config/__init__.py', 'service_semantic_layer/config/__init__.py'),
        ('config/config.py', 'service_semantic_layer/config/config.py'),
    ]
    
    # Embedding Mesh files (flat — no layer/ wrapper)
    embedding_mesh_files = [
        ('embedding_mesh/__init__.py', 'service_semantic_layer/embedding_mesh/__init__.py'),
        ('embedding_mesh/api.py', 'service_semantic_layer/embedding_mesh/api.py'),
        ('embedding_mesh/embeddings_abi.py', 'service_semantic_layer/embedding_mesh/embeddings_abi.py'),
        ('embedding_mesh/weaviate_store.py', 'service_semantic_layer/embedding_mesh/weaviate_store.py'),
        ('embedding_mesh/helpers.py', 'service_semantic_layer/embedding_mesh/helpers.py'),
        ('embedding_mesh/models/__init__.py', 'service_semantic_layer/embedding_mesh/models/__init__.py'),
        ('embedding_mesh/models/models.py', 'service_semantic_layer/embedding_mesh/models/models.py'),
    ]

    # Create all files
    all_files = files_to_create + config_files + embedding_mesh_files
    
    for file_path, template_path in all_files:
        full_path = semantic_dir / file_path
        with open(full_path, 'w') as f:
            f.write(render_template_content(template_path, context))


@click.group()
def create():
    """Create new ABI projects and components
    
    Available commands:
    
    \b
    project    Create a new ABI project with agents, services, and configuration
    swarm      Create a complete ABI Swarm (project + all agents + services)
    
    \b
    Examples:
      abi-core create project my-app --with-semantic-layer
      abi-core create swarm --name abi_swarm
    
    Use 'abi-core create COMMAND --help' for more information on a command.
    """
    pass


@create.command("swarm")
@click.option('--name', '-n', required=True, help='Swarm project name')
@click.option('--description', '-d', default='ABI Swarm - Self-Building Multi-Agent System', help='Project description')
@click.option('--domain', default='general', help='Domain/industry')
@click.option('--model-serving', type=click.Choice(['centralized', 'distributed']), default='centralized', help='Model serving strategy')
def create_swarm(name, description, domain, model_serving):
    """Create a complete ABI Swarm with all agents and services.

    Creates everything in one command — no prompts, no extra steps:
    - Project structure with webapp
    - Semantic layer + Weaviate
    - Guardian + OPA
    - MinIO artifact store
    - Planner, Orchestrator, and Builder agents
    - Docker Compose ready to run

    \b
    Example:
      abi-core create swarm --name abi_swarm
      cd abi_swarm
      docker compose up --build
    """
    import os
    import shutil
    import json
    import yaml

    from rich.progress import Progress, SpinnerColumn, TextColumn

    console.print("\n🚀 Creating ABI Swarm", style="cyan bold")
    console.print("=" * 60, style="cyan")

    # Step 1: Create project with all services (no interactive prompts)
    ctx = click.get_current_context()
    ctx.invoke(
        create_project,
        name=name,
        description=description,
        domain=domain,
        with_semantic_layer=True,
        with_guardian=True,
        model_serving=model_serving,
    )

    # Step 2: cd into project
    project_dir = name.lower().replace(' ', '-').replace('_', '-')
    os.chdir(project_dir)

    # Step 3: Upgrade Guardian service with the new agent from abi-agents
    import abi_agents
    package_root = Path(abi_agents.__file__).parent
    source_guardian_agent = package_root / 'guardian' / 'agent'

    if source_guardian_agent.exists():
        dest_guardian_agent = Path('services/guardian/agent')
        if dest_guardian_agent.exists():
            shutil.rmtree(dest_guardian_agent)
        dest_guardian_agent.mkdir(parents=True)

        for item in source_guardian_agent.iterdir():
            if item.is_file():
                shutil.copy(item, dest_guardian_agent / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_guardian_agent / item.name, dirs_exist_ok=True)

        # Update the service Dockerfile to use the agent's PYTHONPATH
        # The new agent expects to run from /app/agent/ with PYTHONPATH=/app/agent
        guardian_dockerfile = Path('services/guardian/Dockerfile')
        if guardian_dockerfile.exists():
            content = guardian_dockerfile.read_text()
            if 'PYTHONPATH=/app/agent' not in content:
                content = content.replace(
                    'ENV PYTHONPATH=/app',
                    'ENV PYTHONPATH=/app/agent:/app'
                )
            # Remove legacy agent_cards move commands (new agent has cards in the right place)
            lines = content.split('\n')
            lines = [l for l in lines if 'agent_cards/guardian_agent.json' not in l and 'rm -rf /app/agent_cards' not in l]
            guardian_dockerfile.write_text('\n'.join(lines))

    # Step 4: Add swarm agents directly (no prerequisite checks, no prompts)
    runtime_file = Path('.abi/runtime.yaml')
    with open(runtime_file, 'r') as f:
        runtime_config = yaml.safe_load(f) or {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        # Find available ports
        def find_available_port(start_port, used_ports):
            port = start_port
            while port in used_ports:
                port += 1
            return port

        used_ports = set()
        for agent in runtime_config.get('agents', {}).values():
            if 'port' in agent:
                used_ports.add(agent['port'])
        for service in runtime_config.get('services', {}).values():
            if 'port' in service:
                used_ports.add(service['port'])

        planner_port = find_available_port(11437, used_ports)
        used_ports.add(planner_port)
        orchestrator_port = find_available_port(8002, used_ports)
        used_ports.add(orchestrator_port)
        builder_port = find_available_port(11439, used_ports)
        used_ports.add(builder_port)
        web_interface_port = 8083

        # Locate agent source files
        import abi_agents
        package_root = Path(abi_agents.__file__).parent

        # ── Create Planner ──────────────────────────────────────
        task = progress.add_task("Creating Planner Agent...", total=None)
        source_planner = package_root / 'planner'
        if not source_planner.exists():
            console.print(f"❌ Planner source not found at {source_planner}", style="red")
            return

        dest_planner = Path('agents/planner')
        dest_planner.mkdir(parents=True, exist_ok=True)

        for item in (source_planner / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_planner / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_planner / item.name, dirs_exist_ok=True)

        shutil.copy(source_planner / 'Dockerfile', dest_planner / 'Dockerfile')
        shutil.copy(source_planner / 'requirements.txt', dest_planner / 'requirements.txt')
        if (source_planner / 'README.md').exists():
            shutil.copy(source_planner / 'README.md', dest_planner / 'README.md')

        from .add import _generate_agent_card
        planner_agent_card = _generate_agent_card(
            name="Planner Agent",
            description="Decomposes tasks and assigns agents",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-planner:{planner_port}",
            tasks=["decompose complex queries", "assign agents to tasks", "create execution plans", "manage task dependencies"]
        )
        planner_cards_dir = dest_planner / 'agent_cards'
        planner_cards_dir.mkdir(exist_ok=True)
        with open(planner_cards_dir / 'planner_agent.json', 'w') as f:
            json.dump(planner_agent_card, f, indent=2)

        progress.update(task, description="✅ Planner Agent created")

        # ── Create Orchestrator ─────────────────────────────────
        task = progress.add_task("Creating Orchestrator Agent...", total=None)
        source_orch = package_root / 'orchestrator'
        if not source_orch.exists():
            console.print(f"❌ Orchestrator source not found at {source_orch}", style="red")
            return

        dest_orch = Path('agents/orchestrator')
        dest_orch.mkdir(parents=True, exist_ok=True)

        for item in (source_orch / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_orch / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_orch / item.name, dirs_exist_ok=True)

        shutil.copy(source_orch / 'Dockerfile', dest_orch / 'Dockerfile')
        shutil.copy(source_orch / 'requirements.txt', dest_orch / 'requirements.txt')
        if (source_orch / 'README.md').exists():
            shutil.copy(source_orch / 'README.md', dest_orch / 'README.md')

        orchestrator_agent_card = _generate_agent_card(
            name="Abi Orchestrator Agent",
            description="Coordinates multi-agent workflow execution",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-orchestrator:{orchestrator_port}",
            tasks=["coordinate workflows", "execute multi-agent plans", "monitor task execution", "synthesize results"]
        )
        orch_cards_dir = dest_orch / 'agent_cards'
        orch_cards_dir.mkdir(exist_ok=True)
        with open(orch_cards_dir / 'orchestrator_agent.json', 'w') as f:
            json.dump(orchestrator_agent_card, f, indent=2)

        progress.update(task, description="✅ Orchestrator Agent created")

        # ── Create Builder ──────────────────────────────────────
        task = progress.add_task("Creating Builder Agent...", total=None)
        source_builder = package_root / 'builder'
        if not source_builder.exists():
            console.print(f"❌ Builder source not found at {source_builder}", style="red")
            return

        dest_builder = Path('agents/builder')
        dest_builder.mkdir(parents=True, exist_ok=True)

        for item in (source_builder / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_builder / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_builder / item.name, dirs_exist_ok=True)

        shutil.copy(source_builder / 'Dockerfile', dest_builder / 'Dockerfile')
        shutil.copy(source_builder / 'requirements.txt', dest_builder / 'requirements.txt')
        if (source_builder / 'README.md').exists():
            shutil.copy(source_builder / 'README.md', dest_builder / 'README.md')

        builder_agent_card = _generate_agent_card(
            name="Builder Agent",
            description="Builds and deploys ephemeral AI agents on demand",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-builder:{builder_port}",
            tasks=["build ephemeral agents", "create MCP tools", "deploy containers", "manage agent lifecycle"]
        )
        builder_agent_card["permissions"] = ["register_agents", "unregister_agents"]
        builder_cards_dir = dest_builder / 'agent_cards'
        builder_cards_dir.mkdir(exist_ok=True)
        with open(builder_cards_dir / 'builder_agent.json', 'w') as f:
            json.dump(builder_agent_card, f, indent=2)

        progress.update(task, description="✅ Builder Agent created")

        # ── Create Guardian agent card ──────────────────────────
        task = progress.add_task("Creating Guardian agent card...", total=None)
        guardian_agent_card = _generate_agent_card(
            name="Guardian Agent",
            description="Guards execution by validating intents and actions against security policies",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-guardian:11438",
            tasks=["validate_query", "guardian_security", "policy_validation", "risk_assessment"]
        )
        guardian_cards_dir = Path('services/guardian/agent/agent_cards')
        guardian_cards_dir.mkdir(parents=True, exist_ok=True)
        with open(guardian_cards_dir / 'guardian_agent.json', 'w') as f:
            json.dump(guardian_agent_card, f, indent=2)
        progress.update(task, description="✅ Guardian agent card created")

        # ── Copy agent cards to semantic layer ──────────────────
        task = progress.add_task("Copying cards to semantic layer...", total=None)
        semantic_service_dir = None
        services_dir = Path('services')
        if services_dir.exists():
            for service_path in services_dir.iterdir():
                if service_path.is_dir():
                    if (service_path / 'embedding_mesh').exists():
                        semantic_service_dir = service_path
                        break

        if semantic_service_dir:
            semantic_agent_cards_dir = semantic_service_dir / 'agent_cards'
            semantic_agent_cards_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(planner_cards_dir / 'planner_agent.json', semantic_agent_cards_dir / 'planner_agent.json')
            shutil.copy(orch_cards_dir / 'orchestrator_agent.json', semantic_agent_cards_dir / 'orchestrator_agent.json')
            shutil.copy(builder_cards_dir / 'builder_agent.json', semantic_agent_cards_dir / 'builder_agent.json')
            shutil.copy(guardian_cards_dir / 'guardian_agent.json', semantic_agent_cards_dir / 'guardian_agent.json')

            # Copy tool cards if available
            semantic_tool_cards_dir = semantic_service_dir / 'tool_cards'
            semantic_tool_cards_dir.mkdir(parents=True, exist_ok=True)
            try:
                import abi_core
                abi_core_root = Path(abi_core.__file__).parent.parent.parent.parent.parent
                tool_cards_sources = [
                    abi_core_root / 'abi-image' / 'tool_cards',
                    Path(__file__).parent.parent.parent / 'tool_cards',
                ]
                for source_dir in tool_cards_sources:
                    if source_dir.exists():
                        for tc_file in source_dir.glob('*.json'):
                            shutil.copy(tc_file, semantic_tool_cards_dir / tc_file.name)
                        break
            except Exception:
                pass

        progress.update(task, description="✅ Agent cards copied to semantic layer")

        # ── Update runtime.yaml ─────────────────────────────────
        task = progress.add_task("Updating runtime.yaml...", total=None)
        from .utils import update_runtime_config

        # Ensure project section has model_serving
        update_runtime_config('project', {
            'name': name,
            'model_serving': model_serving,
            'default_model': 'qwen2.5:3b',
        })

        update_runtime_config('agents', {
            'planner': {
                'name': 'Planner Agent',
                'description': 'Decomposes tasks and assigns agents',
                'port': planner_port,
                'type': 'planner',
                'path': 'agents/planner'
            },
            'orchestrator': {
                'name': 'Orchestrator Agent',
                'description': 'Coordinates multi-agent workflow execution',
                'port': orchestrator_port,
                'type': 'orchestrator',
                'path': 'agents/orchestrator'
            },
            'builder': {
                'name': 'Builder Agent',
                'description': 'Builds and deploys ephemeral AI agents on demand',
                'port': builder_port,
                'type': 'builder',
                'path': 'agents/builder'
            }
        })
        progress.update(task, description="✅ runtime.yaml updated")

        # ── Update compose.yaml ─────────────────────────────────
        task = progress.add_task("Updating compose.yaml...", total=None)

        # Reload runtime for compose update — ensure our ports are there
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}

        # Force correct ports in runtime_config to avoid stale data
        if 'agents' not in runtime_config:
            runtime_config['agents'] = {}
        runtime_config['agents']['planner'] = runtime_config.get('agents', {}).get('planner', {})
        runtime_config['agents']['planner']['port'] = planner_port
        runtime_config['agents']['orchestrator'] = runtime_config.get('agents', {}).get('orchestrator', {})
        runtime_config['agents']['orchestrator']['port'] = orchestrator_port
        runtime_config['agents']['builder'] = runtime_config.get('agents', {}).get('builder', {})
        runtime_config['agents']['builder']['port'] = builder_port

        from .add import _update_compose_with_orchestration
        _update_compose_with_orchestration(runtime_config)

        progress.update(task, description="✅ compose.yaml updated")

    console.print("\n" + "=" * 60, style="green")
    console.print("✅ ABI Swarm created successfully!", style="green bold")
    console.print("=" * 60, style="green")
    console.print(f"\n📁 Location: {Path.cwd()}", style="blue")
    console.print(f"\n▶️  To start:", style="cyan")
    console.print(f"   cd {project_dir}", style="blue")
    console.print(f"   docker compose up --build -d", style="blue")
    console.print(f"\n🧪 To test:", style="cyan")
    console.print(f"   curl -X POST http://localhost:{web_interface_port}/stream \\", style="blue")
    console.print(f'     -H "Content-Type: application/json" \\', style="blue")
    console.print(f'     -d \'{{"query": "hello", "context_id": "test", "task_id": "task1"}}\'', style="blue")


@create.command("project")
@click.option('--name', '-n', required=True, help='Project name')
@click.option('--description', '-d', help='Project description')
@click.option('--domain', help='Domain/industry (e.g., finance, healthcare)')
@click.option('--with-semantic-layer', is_flag=True, help='Include AI agent discovery and routing service')
@click.option('--with-guardian', is_flag=True, help='Include security policy enforcement service')
@click.option('--model-serving', type=click.Choice(['centralized', 'distributed']), default=None, help='Model serving strategy: centralized (shared Ollama) or distributed (each agent has own Ollama)')
def create_project(name, description, domain, with_semantic_layer, with_guardian, model_serving):
    """Create a new ABI project with agents, services, and configuration
    
    Creates a complete ABI project structure including:
    - Project configuration and metadata
    - Docker Compose setup for containerization
    - Optional semantic layer for agent discovery
    - Optional guardian service for security policies
    
    \b
    Examples:
      abi-core create project my-app --name my-app
      abi-core create project fintech --name fintech --domain finance --with-semantic-layer
      abi-core create project secure-app --name secure-app --with-guardian --with-semantic-layer
    
    The project will be created in a new directory with the specified name.
    """
    
    # Interactive prompts if not provided
    if not description:
        description = Prompt.ask("Project description", default=f"ABI-powered {name} project")
    
    if not domain:
        domain = Prompt.ask("Domain/Industry", default="general")
    
    if not with_semantic_layer:
        with_semantic_layer = Confirm.ask("Include semantic layer service?", default=True)
    
    if not with_guardian:
        with_guardian = Confirm.ask("Include guardian security service?", default=True)
    
    # Ask about model serving strategy if not provided
    if not model_serving:
        console.print("\n💡 Model Serving Strategy:", style="cyan bold")
        console.print("  • centralized: Single shared Ollama for all agents (recommended for production)", style="dim")
        console.print("  • distributed: Each agent has its own Ollama (recommended for development)", style="dim")
        model_serving = Prompt.ask(
            "\nChoose model serving strategy",
            choices=["centralized", "distributed"],
            default="distributed"
        )
    
    project_dir = Path(name.lower().replace(' ', '-').replace('_', '-'))
    
    if project_dir.exists():
        console.print(f"❌ Directory '{project_dir}' already exists", style="red")
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task("Creating project structure...", total=None)
        
        # Template context
        context = {
            'project_name': name,
            'project_dir': project_dir.name,
            'description': description,
            'domain': domain,
            'with_semantic_layer': with_semantic_layer,
            'with_guardian': with_guardian,
            'model_serving': model_serving,
            'is_centralized': model_serving == 'centralized',
            'is_distributed': model_serving == 'distributed',
            'service_name': name,
            'service_class_name': name.replace(' ', '').replace('-', '').replace('_', ''),
            'version': '1.0.0',
            'timestamp': '2024-01-01T00:00:00Z',
            # Additional variables for runtime.yaml template
            'model_name': 'qwen2.5:3b',
            'embedding_model': 'nomic-embed-text:v1.5',
            'dashboard_port': '8080',
            'opa_url': f'http://{project_dir.name}-opa:8181',
            'max_risk_threshold': '0.7',
            'mode': 'development',
            'log_level': 'INFO',
            'debug': 'true',
            'compliance_required': 'true',
            'audit_all_transactions': 'true',
            'max_transaction_amount': '10000.0',
            'hipaa_compliance': 'true',
            'phi_protection': 'true',
            'audit_patient_access': 'true'
        }
        
        # Create project structure
        project_dir.mkdir()
        
        # Agents directory
        (project_dir / 'agents').mkdir()
        
        # Services directory
        (project_dir / 'services').mkdir()
        
        # Web API directory (main application) inside services
        web_api_dir = project_dir / 'services' / 'web_api'
        web_api_dir.mkdir()
        
        # Config inside web_api
        (web_api_dir / 'config').mkdir()
        (web_api_dir / 'config' / '__init__.py').touch()
        with open(web_api_dir / 'config' / 'config.py', 'w') as f:
            f.write(render_template_content('project/config/config.py', context))
        
        if with_semantic_layer:
            console.print("🔄 Creating semantic layer service...")
            semantic_dir = project_dir / 'services' / 'semantic_layer'
            semantic_dir.mkdir()
            
            # Generate complete semantic layer structure
            _create_semantic_layer_structure(semantic_dir, context)
        
        if with_guardian:
            console.print("🛡️  Creating Guardian security service...")
            guardian_dir = project_dir / 'services' / 'guardian'
            guardian_dir.mkdir()
            
            # Create directory structure
            agent_dir = guardian_dir / 'agent'
            agent_dir.mkdir()
            models_dir = agent_dir / 'models'
            models_dir.mkdir()
            
            # Create emergency_logs directory
            emergency_logs_dir = guardian_dir / 'emergency_logs'
            emergency_logs_dir.mkdir()
            (emergency_logs_dir / '.gitkeep').touch()
            
            # Create OPA directory structure
            opa_dir = guardian_dir / 'opa'
            opa_dir.mkdir()
            policies_dir = opa_dir / 'policies'
            policies_dir.mkdir()
            
            # Guardian config files (inside agent/)
            guardian_config_files = [
                ('agent/config/__init__.py', 'service_guardian/agent/config/__init__.py'),
                ('agent/config/config.py', 'service_guardian/agent/config/config.py'),
            ]
            
            # Guardian agent files
            guardian_files = [
                ('agent/__init__.py', 'service_guardian/agent/__init__.py'),
                ('agent/app.py', 'service_guardian/agent/app.py'),
                ('agent/guardian.py', 'service_guardian/agent/guardian.py'),
                ('agent/main.py', 'service_guardian/agent/main.py'),
                ('agent/policy_engine_secure.py', 'service_guardian/agent/policy_engine_secure.py'),
                ('agent/Dockerfile', 'service_guardian/agent/Dockerfile'),
                ('agent/agent_cards/guardian_agent.json', 'service_guardian/agent/agent_cards/guardian_agent.json'),
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
                ('opa/Dockerfile', 'service_guardian/opa/Dockerfile'),
                ('opa/policies/basic.rego', 'service_guardian/opa/policies/basic.rego'),
                ('opa/policies/semantic_access.rego', 'service_guardian/opa/policies/semantic_access.rego'),
                ('opa/policies/a2a_access.rego', 'service_guardian/opa/policies/a2a_access.rego'),
            ]
            
            # Create all Guardian files
            all_guardian_files = guardian_config_files + guardian_files + root_files + opa_files
            
            template_dir = Path(__file__).parent.parent.parent / 'scaffolding'
            
            for file_path, template_path in all_guardian_files:
                full_path = guardian_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # For .rego files and agent card JSONs, copy directly without template rendering
                if file_path.endswith('.rego') or 'agent_cards/' in file_path:
                    source_file = template_dir / template_path
                    if source_file.exists():
                        with open(source_file, 'r') as src:
                            with open(full_path, 'w') as dst:
                                dst.write(src.read())
                    else:
                        console.print(f"⚠️  Warning: {source_file} not found", style="yellow")
                else:
                    with open(full_path, 'w') as f:
                        f.write(render_template_content(template_path, context))
        
            # Copy guardian agent card to semantic layer
            if with_semantic_layer:
                import shutil
                # Generate guardian agent card with correct project URL
                guardian_card_data = {
                    "name": "Guardian Agent",
                    "description": "Guards execution by validating intents, actions, and artifacts against organizational and regulatory policies.",
                    "url": f"http://{project_dir}-guardian:{context.get('guardian_port', 11438)}",
                    "version": "1.0.0",
                    "capabilities": {"streaming": "False", "pushNotifications": "True", "stateTransitionHistory": "True"},
                    "defaultInputModes": ["application/json", "text/plain"],
                    "defaultOutputModes": ["application/json", "text/plain"],
                    "skills": [
                        {"id": "policy_validate", "name": "Policy Validation", "description": "Validate actions against OPA policies", "tags": ["compliance", "policy", "validation", "guardian", "security"]},
                        {"id": "semantic_compliance", "name": "Semantic Compliance", "description": "Detect policy violations via semantic analysis", "tags": ["semantic", "compliance", "safety"]},
                        {"id": "action_gatekeeping", "name": "Action Gatekeeping", "description": "Approve, modify, or reject proposed actions", "tags": ["authorization", "gatekeeping"]},
                        {"id": "risk_scoring", "name": "Risk Scoring", "description": "Assign deviation and risk scores", "tags": ["risk", "scoring"]},
                    ],
                }
                import json as _json
                # Write to guardian directory
                guardian_cards_dir = guardian_dir / 'agent' / 'agent_cards'
                guardian_cards_dir.mkdir(parents=True, exist_ok=True)
                with open(guardian_cards_dir / 'guardian_agent.json', 'w') as f:
                    _json.dump(guardian_card_data, f, indent=2)
                # Copy to semantic layer
                semantic_cards_dir = project_dir / 'services' / 'semantic_layer' / 'agent_cards'
                if semantic_cards_dir.exists():
                    with open(semantic_cards_dir / 'guardian_agent.json', 'w') as f:
                        _json.dump(guardian_card_data, f, indent=2)

        # ABI directory
        (project_dir / '.abi').mkdir()
        with open(project_dir / '.abi' / 'runtime.yaml', 'w') as f:
            f.write(render_template_content('project/.abi/runtime.yaml', context))
        
        # Web API files (moved from root)
        with open(web_api_dir / 'requirements.txt', 'w') as f:
            f.write(render_template_content('project/requirements.txt', context))
        
        with open(web_api_dir / 'Dockerfile', 'w') as f:
            f.write(render_template_content('project/Dockerfile', context))
        
        with open(web_api_dir / 'main.py', 'w') as f:
            f.write(render_template_content('project/main.py', context))
        
        # Service cards for webapp MCP authentication
        if with_semantic_layer:
            service_cards_dir = web_api_dir / 'service_cards'
            service_cards_dir.mkdir()
            webapp_card_content = render_template_content('project/service_cards/webapp.json', context)
            with open(service_cards_dir / 'webapp.json', 'w') as f:
                f.write(webapp_card_content)
            # Copy to semantic layer so it can validate the webapp identity at startup
            semantic_service_cards = semantic_dir / 'service_cards'
            semantic_service_cards.mkdir(exist_ok=True)
            with open(semantic_service_cards / 'webapp.json', 'w') as f:
                f.write(webapp_card_content)
        
        # Root files (only compose and README stay in root)
        with open(project_dir / 'compose.yaml', 'w') as f:
            f.write(render_template_content('project/compose.yaml', context))
        
        with open(project_dir / 'README.md', 'w') as f:
            f.write(render_template_content('project/README.md', context))
        
        # Interactive console (TUI)
        with open(project_dir / 'console.py', 'w') as f:
            f.write(render_template_content('project/console.py', context))
        
        progress.update(task, description="Project created successfully!", completed=True)
    
    console.print(f"\n✅ Project '{name}' created successfully!", style="green")
    console.print(f"📁 Location: {project_dir.absolute()}", style="blue")
    
    # Show next steps
    console.print("\n📋 Next steps:", style="cyan")
    console.print(f"   cd {project_dir}")
    console.print("   abi-core add agent --name YourAgent")
    console.print("   abi-core run")


def _get_semantic_main_template(context):
    """Get semantic layer main template"""
    return f'''#!/usr/bin/env python3
"""
Semantic Layer Service Main
{context.get('project_name', 'ABI Project')} - {context.get('domain', 'general')} Domain
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Configuration
AGENT_CARDS_DIR = os.getenv("AGENT_CARDS_BASE", "./agent_cards")
MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

app = FastAPI(
    title="Semantic Layer Service",
    description="Semantic layer for {context.get('project_name', 'ABI Project')} - {context.get('domain', 'general')} domain",
    version="1.0.0"
)

# Global agent cards cache
_agent_cards_cache: Optional[List[Dict[str, Any]]] = None

def load_agent_cards() -> List[Dict[str, Any]]:
    """Load all agent cards from the agent_cards directory"""
    global _agent_cards_cache
    
    if _agent_cards_cache is not None:
        return _agent_cards_cache
    
    cards_dir = Path(AGENT_CARDS_DIR)
    agent_cards = []
    
    if not cards_dir.exists():
        logger.warning(f"Agent cards directory not found: {{cards_dir}}")
        return []
    
    for card_file in cards_dir.glob("*.json"):
        try:
            with open(card_file, 'r') as f:
                card_data = json.load(f)
                agent_cards.append(card_data)
                logger.info(f"Loaded agent card: {{card_data.get('name', 'Unknown')}}")
        except Exception as e:
            logger.error(f"Error loading agent card {{card_file}}: {{e}}")
    
    _agent_cards_cache = agent_cards
    logger.info(f"Loaded {{len(agent_cards)}} agent cards")
    return agent_cards

def find_best_agent(query: str) -> Optional[Dict[str, Any]]:
    """Find the best matching agent for a query using simple text matching"""
    agent_cards = load_agent_cards()
    
    if not agent_cards:
        return None
    
    query_lower = query.lower()
    best_match = None
    best_score = 0
    
    for card in agent_cards:
        score = 0
        
        # Check name match
        if query_lower in card.get('name', '').lower():
            score += 3
        
        # Check description match
        if query_lower in card.get('description', '').lower():
            score += 2
        
        # Check supported tasks
        for task in card.get('supportedTasks', []):
            if query_lower in task.lower():
                score += 2
        
        # Check skills
        for skill in card.get('skills', []):
            if query_lower in skill.get('name', '').lower():
                score += 1
            if query_lower in skill.get('description', '').lower():
                score += 1
        
        if score > best_score:
            best_score = score
            best_match = card
    
    return best_match

@app.get("/")
async def root():
    agent_count = len(load_agent_cards())
    return {{
        "message": "Semantic Layer Service",
        "status": "running",
        "project": "{context.get('project_name', 'ABI Project')}",
        "domain": "{context.get('domain', 'general')}",
        "registered_agents": agent_count
    }}

@app.get("/health")
async def health():
    agent_cards = load_agent_cards()
    return {{
        "status": "healthy",
        "service": "semantic_layer",
        "agent_cards_loaded": len(agent_cards),
        "agent_cards_directory": AGENT_CARDS_DIR
    }}

@app.get("/v1/agents")
async def list_agents():
    """List all registered agents"""
    agent_cards = load_agent_cards()
    return {{
        "agents": [
            {{
                "id": card.get("id"),
                "name": card.get("name"),
                "description": card.get("description"),
                "url": card.get("url"),
                "tasks": card.get("supportedTasks", [])
            }}
            for card in agent_cards
        ],
        "total": len(agent_cards)
    }}

@app.get("/v1/tools")
async def get_tools():
    return {{
        "tools": [
            {{
                "name": "find_agent",
                "description": "Find agents by natural language query",
                "parameters": {{"query": "string"}}
            }},
            {{
                "name": "list_agents",
                "description": "List all registered agents",
                "parameters": {{}}
            }},
            {{
                "name": "get_agent",
                "description": "Get specific agent by ID",
                "parameters": {{"agent_id": "string"}}
            }}
        ]
    }}

@app.post("/v1/tools/find_agent")
async def find_agent_tool(request: dict):
    """Find agent tool for MCP protocol"""
    query = request.get("query", "")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    
    best_agent = find_best_agent(query)
    
    if not best_agent:
        return {{
            "content": [
                {{
                    "type": "text",
                    "text": f"No suitable agent found for query: {{query}}"
                }}
            ]
        }}
    
    return {{
        "content": [
            {{
                "type": "text", 
                "text": f"Found agent: {{best_agent.get('name')}} - {{best_agent.get('description')}}"
            }}
        ],
        "agent_card": best_agent
    }}

@app.post("/v1/tools/get_agent")
async def get_agent_tool(request: dict):
    """Get specific agent by ID"""
    agent_id = request.get("agent_id", "")
    
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id parameter is required")
    
    agent_cards = load_agent_cards()
    
    for card in agent_cards:
        if card.get("id") == agent_id:
            return {{
                "content": [
                    {{
                        "type": "text",
                        "text": f"Agent: {{card.get('name')}} - {{card.get('description')}}"
                    }}
                ],
                "agent_card": card
            }}
    
    raise HTTPException(status_code=404, detail=f"Agent not found: {{agent_id}}")

@app.post("/v1/register_agent")
async def register_agent(agent_card: dict):
    """Register a new agent (for dynamic registration)"""
    global _agent_cards_cache
    
    # Validate required fields
    required_fields = ["id", "name", "description", "url"]
    for field in required_fields:
        if field not in agent_card:
            raise HTTPException(status_code=400, detail=f"Missing required field: {{field}}")
    
    # Save to file
    agent_id = agent_card["id"].replace("agent://", "").replace("/", "_")
    card_file = Path(AGENT_CARDS_DIR) / f"{{agent_id}}_agent.json"
    
    try:
        with open(card_file, 'w') as f:
            json.dump(agent_card, f, indent=2)
        
        # Clear cache to force reload
        _agent_cards_cache = None
        
        logger.info(f"Registered new agent: {{agent_card.get('name')}}")
        
        return {{
            "message": "Agent registered successfully",
            "agent_id": agent_card["id"],
            "file": str(card_file)
        }}
    
    except Exception as e:
        logger.error(f"Error registering agent: {{e}}")
        raise HTTPException(status_code=500, detail=f"Failed to register agent: {{str(e)}}")

@app.delete("/v1/agents/{{agent_id}}")
async def unregister_agent(agent_id: str):
    """Unregister an agent (remove from registry)"""
    global _agent_cards_cache
    
    # Find and remove the agent card file
    cards_dir = Path(AGENT_CARDS_DIR)
    agent_file_id = agent_id.replace("agent://", "").replace("/", "_")
    
    for card_file in cards_dir.glob(f"*{{agent_file_id}}*.json"):
        try:
            card_file.unlink()
            _agent_cards_cache = None  # Clear cache
            logger.info(f"Unregistered agent: {{agent_id}}")
            
            return {{
                "message": "Agent unregistered successfully",
                "agent_id": agent_id,
                "file_removed": str(card_file)
            }}
        except Exception as e:
            logger.error(f"Error unregistering agent: {{e}}")
            raise HTTPException(status_code=500, detail=f"Failed to unregister agent: {{str(e)}}")
    
    raise HTTPException(status_code=404, detail=f"Agent not found: {{agent_id}}")

if __name__ == "__main__":
    # Load agent cards on startup
    load_agent_cards()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=10100,
        reload=True
    )
'''


def _get_semantic_requirements_template():
    """Get semantic layer requirements template"""
    return '''# Semantic Layer Service Requirements
fastapi>=0.135.0
uvicorn[standard]>=0.42.0
pydantic>=2.12.0
requests>=2.32.0
httpx>=0.28.0
fastmcp>=3.2.0
weaviate-client>=4.12.0
numpy>=2.4.0
pandas>=3.0.0
ollama>=0.4.0
starlette>=1.0.0
'''


def _get_semantic_dockerfile_template():
    """Get semantic layer Dockerfile template"""
    return '''# Semantic Layer Service Dockerfile
FROM agentbase/abi-image-v2:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy service files
COPY . .

# Create agent_cards directory if it doesn't exist
RUN mkdir -p /app/agent_cards

# Expose port
EXPOSE 10100

# Environment variables
ENV ABI_ROLE="Semantic Layer"
ENV ABI_NODE="ABI Node"
ENV PYTHONPATH=/app
ENV AGENT_CARDS_BASE="/app/agent_cards"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:10100/health || exit 1

# Run
CMD ["python", "main.py"]
'''


