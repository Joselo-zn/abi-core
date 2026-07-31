"""
`add abi-swarm` — scaffold the Planner/Orchestrator/Builder multi-agent bundle.
"""

import click
from pathlib import Path

from ..utils import console, update_runtime_config
from .shared import _generate_agent_card
from .service import add_semantic_layer, add_service


@click.command("abi-swarm")
def add_abi_swarm():
    """Add Planner and Orchestrator agents for multi-agent workflow coordination

    This command sets up the complete agentic orchestration system by adding:
    - Planner Agent: Decomposes tasks and assigns agents
    - Orchestrator Agent: Coordinates workflow execution and synthesizes results

    \b
    Prerequisites:
    - Guardian service must be configured
    - Semantic layer service must be configured

    \b
    Example:
      abi-core add abi-swarm
    """
    import shutil
    import yaml

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory.", style="red")
        console.print("💡 Run 'abi-core create project' first.", style="yellow")
        return

    runtime_file = Path('.abi/runtime.yaml')
    if not runtime_file.exists():
        console.print("❌ runtime.yaml not found", style="red")
        return

    console.print("\n🚀 Setting up ABI Swarm", style="cyan bold")
    console.print("=" * 60, style="cyan")

    # Read runtime.yaml
    with open(runtime_file, 'r') as f:
        runtime_config = yaml.safe_load(f) or {}

    # Get project name and directory from runtime.yaml
    project_name = runtime_config.get('project', {}).get('name', Path.cwd().name)
    project_dir = project_name.lower().replace(' ', '-').replace('_', '-')

    # Auto-add prerequisites if missing
    console.print("\n📋 Checking prerequisites...", style="cyan")

    services = runtime_config.get('services', {})

    has_guardian = any(
        service.get('type') in ['guardian', 'guardian-native']
        for service in services.values()
    )

    has_semantic_layer = any(
        service.get('type') == 'semantic-layer'
        for service in services.values()
    )

    if not has_semantic_layer:
        console.print("[🔧] Semantic layer not found — adding automatically...", style="cyan")
        from click import Context
        ctx = Context(add_semantic_layer)
        ctx.invoke(add_semantic_layer, domain='general')
        # Reload runtime after adding
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
        console.print("✅ Semantic layer added", style="green")
    else:
        console.print("✅ Semantic layer found", style="green")

    if not has_guardian:
        console.print("[🔧] Guardian not found — adding automatically...", style="cyan")
        # Find the guardian-native command
        from click import Context
        ctx = Context(add_service)
        ctx.invoke(add_service, service_type='guardian-native', name=None, domain='general')
        # Reload runtime after adding
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}
        console.print("✅ Guardian added", style="green")
    else:
        console.print("✅ Guardian found", style="green")

    # Check if already exists
    agents = runtime_config.get('agents', {})
    if 'planner' in agents or 'orchestrator' in agents or 'builder' in agents:
        console.print("\n⚠️  Planner, Orchestrator, or Builder already exists", style="yellow")
        from rich.prompt import Confirm
        if not Confirm.ask("Do you want to recreate them?"):
            return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        # Find available ports dynamically FIRST
        def find_available_port(start_port: int, used_ports: set) -> int:
            """Find next available port starting from start_port"""
            port = start_port
            while port in used_ports:
                port += 1
            return port

        # Collect all used ports
        used_ports = set()
        for agent in runtime_config.get('agents', {}).values():
            if 'port' in agent:
                used_ports.add(agent['port'])
        for service in runtime_config.get('services', {}).values():
            if 'port' in service:
                used_ports.add(service['port'])

        # Assign dynamic ports
        planner_port = find_available_port(11437, used_ports)
        used_ports.add(planner_port)
        orchestrator_port = find_available_port(8002, used_ports)
        web_interface_port = 8083

        # Create Planner
        task = progress.add_task("Creating Planner Agent...", total=None)

        # Try to find source files (works in both dev and installed)
        import abi_agents
        package_root = Path(abi_agents.__file__).parent
        source_planner = package_root / 'planner'

        if not source_planner.exists():
            console.print(f"❌ Planner source not found at {source_planner}", style="red")
            return

        dest_planner = Path('agents/planner')

        if dest_planner.exists():
            shutil.rmtree(dest_planner)

        dest_planner.mkdir(parents=True)

        # Copy planner files (copy contents of agent/ to root for consistency)
        for item in (source_planner / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_planner / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_planner / item.name)

        shutil.copy(source_planner / 'Dockerfile', dest_planner / 'Dockerfile')
        shutil.copy(source_planner / 'requirements.txt', dest_planner / 'requirements.txt')
        if (source_planner / 'README.md').exists():
            shutil.copy(source_planner / 'README.md', dest_planner / 'README.md')

        # Generate and save Planner agent card
        progress.update(task, description="Generating Planner agent card...")
        planner_agent_card = _generate_agent_card(
            name="Planner Agent",
            description="Decomposes tasks and assigns agents",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-planner:{planner_port}",
            tasks=["decompose complex queries", "assign agents to tasks", "create execution plans", "manage task dependencies"]
        )

        # Save Planner agent card
        planner_agent_cards_dir = dest_planner / 'agent_cards'
        planner_agent_cards_dir.mkdir(exist_ok=True)
        import json
        with open(planner_agent_cards_dir / 'planner_agent.json', 'w') as f:
            json.dump(planner_agent_card, f, indent=2)

        progress.update(task, description="✅ Planner Agent created")

        # Create Orchestrator
        task = progress.add_task("Creating Orchestrator Agent...", total=None)

        source_orch = package_root / 'orchestrator'

        if not source_orch.exists():
            console.print(f"❌ Orchestrator source not found at {source_orch}", style="red")
            return

        dest_orch = Path('agents/orchestrator')

        if dest_orch.exists():
            shutil.rmtree(dest_orch)

        dest_orch.mkdir(parents=True)

        # Copy orchestrator files (copy contents of agent/ to root for consistency)
        for item in (source_orch / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_orch / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_orch / item.name)

        shutil.copy(source_orch / 'Dockerfile', dest_orch / 'Dockerfile')
        shutil.copy(source_orch / 'requirements.txt', dest_orch / 'requirements.txt')
        if (source_orch / 'README.md').exists():
            shutil.copy(source_orch / 'README.md', dest_orch / 'README.md')

        # Generate and save Orchestrator agent card
        progress.update(task, description="Generating Orchestrator agent card...")
        orchestrator_agent_card = _generate_agent_card(
            name="Abi Orchestrator Agent",
            description="Coordinates multi-agent workflow execution",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-orchestrator:{orchestrator_port}",
            tasks=["coordinate workflows", "execute multi-agent plans", "monitor task execution", "synthesize results"]
        )

        # Save Orchestrator agent card
        orchestrator_agent_cards_dir = dest_orch / 'agent_cards'
        orchestrator_agent_cards_dir.mkdir(exist_ok=True)
        with open(orchestrator_agent_cards_dir / 'orchestrator_agent.json', 'w') as f:
            json.dump(orchestrator_agent_card, f, indent=2)

        progress.update(task, description="✅ Orchestrator Agent created")

        # Create Builder
        task = progress.add_task("Creating Builder Agent...", total=None)

        source_builder = package_root / 'builder'

        if not source_builder.exists():
            console.print(f"❌ Builder source not found at {source_builder}", style="red")
            return

        builder_port = find_available_port(11439, used_ports)
        used_ports.add(builder_port)

        dest_builder = Path('agents/builder')

        if dest_builder.exists():
            shutil.rmtree(dest_builder)

        dest_builder.mkdir(parents=True)

        for item in (source_builder / 'agent').iterdir():
            if item.is_file():
                shutil.copy(item, dest_builder / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_builder / item.name)

        shutil.copy(source_builder / 'Dockerfile', dest_builder / 'Dockerfile')
        shutil.copy(source_builder / 'requirements.txt', dest_builder / 'requirements.txt')
        if (source_builder / 'README.md').exists():
            shutil.copy(source_builder / 'README.md', dest_builder / 'README.md')

        progress.update(task, description="Generating Builder agent card...")
        builder_agent_card = _generate_agent_card(
            name="Builder Agent",
            description="Builds and deploys ephemeral AI agents on demand",
            model="qwen2.5:3b",
            url=f"http://{project_dir}-builder:{builder_port}",
            tasks=["build ephemeral agents", "create MCP tools", "deploy containers", "manage agent lifecycle"]
        )
        builder_agent_card["permissions"] = ["register_agents", "unregister_agents"]

        builder_agent_cards_dir = dest_builder / 'agent_cards'
        builder_agent_cards_dir.mkdir(exist_ok=True)
        with open(builder_agent_cards_dir / 'builder_agent.json', 'w') as f:
            json.dump(builder_agent_card, f, indent=2)

        progress.update(task, description="✅ Builder Agent created")

        # Copy agent cards to semantic layer
        task = progress.add_task("Copying agent cards to semantic layer...", total=None)

        # Find semantic layer directory
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
            semantic_agent_cards_dir = semantic_service_dir / 'agent_cards'
            semantic_agent_cards_dir.mkdir(parents=True, exist_ok=True)

            # Copy Planner agent card
            shutil.copy(
                dest_planner / 'agent_cards' / 'planner_agent.json',
                semantic_agent_cards_dir / 'planner_agent.json'
            )

            # Copy Orchestrator agent card
            shutil.copy(
                dest_orch / 'agent_cards' / 'orchestrator_agent.json',
                semantic_agent_cards_dir / 'orchestrator_agent.json'
            )

            # Copy Builder agent card
            shutil.copy(
                dest_builder / 'agent_cards' / 'builder_agent.json',
                semantic_agent_cards_dir / 'builder_agent.json'
            )

            # Copy example tool cards from abi-image
            semantic_tool_cards_dir = semantic_service_dir / 'tool_cards'
            semantic_tool_cards_dir.mkdir(parents=True, exist_ok=True)

            try:
                import abi_core
                abi_core_root = Path(abi_core.__file__).parent.parent.parent.parent.parent
                # tool_cards live in abi-image/tool_cards/ relative to the repo
                # But in installed package, they're bundled — try multiple paths
                tool_cards_sources = [
                    abi_core_root / 'abi-image' / 'tool_cards',
                    Path(__file__).parent.parent.parent / 'tool_cards',
                ]

                for source_dir in tool_cards_sources:
                    if source_dir.exists():
                        for tc_file in source_dir.glob('*.json'):
                            shutil.copy(tc_file, semantic_tool_cards_dir / tc_file.name)
                            console.print(f"  Copied tool card: {tc_file.name}")
                        break
            except Exception as e:
                console.print(f"[⚠️] Could not copy example tool cards: {e}")

            progress.update(task, description="✅ Agent & tool cards copied to semantic layer")
        else:
            progress.update(task, description="⚠️  Semantic layer not found, skipping card copy")

        # Update runtime.yaml
        task = progress.add_task("Updating runtime.yaml...", total=None)

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

        # Register agent cards
        update_runtime_config('agent_cards', {
            'planner': {
                'name': 'Planner Agent',
                'description': 'Decomposes tasks and assigns agents',
                'model': 'qwen2.5:3b',
                'url': f'http://{project_dir}-planner:{planner_port}',
                'tasks': [
                    'decompose complex queries',
                    'assign agents to tasks',
                    'create execution plans',
                    'manage task dependencies'
                ],
                'locations': [
                    'services/semantic_layer/agent_cards/planner_agent.json',
                    'agents/planner/agent_cards/planner_agent.json'
                ]
            },
            'orchestrator': {
                'name': 'Abi Orchestrator Agent',
                'description': 'Coordinates multi-agent workflow execution',
                'model': 'qwen2.5:3b',
                'url': f'http://{project_dir}-orchestrator:{orchestrator_port}',
                'tasks': [
                    'coordinate workflows',
                    'execute multi-agent plans',
                    'monitor task execution',
                    'synthesize results'
                ],
                'locations': [
                    'services/semantic_layer/agent_cards/orchestrator_agent.json',
                    'agents/orchestrator/agent_cards/orchestrator_agent.json'
                ]
            },
            'builder': {
                'name': 'Builder Agent',
                'description': 'Builds and deploys ephemeral AI agents on demand',
                'model': 'qwen2.5:3b',
                'url': f'http://{project_dir}-builder:{builder_port}',
                'tasks': [
                    'build ephemeral agents',
                    'create MCP tools',
                    'deploy containers',
                    'manage agent lifecycle'
                ],
                'locations': [
                    'services/semantic_layer/agent_cards/builder_agent.json',
                    'agents/builder/agent_cards/builder_agent.json'
                ]
            }
        })

        progress.update(task, description="✅ runtime.yaml updated")

        # Reload runtime.yaml to get updated configuration
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f) or {}

        # Update compose.yaml
        task = progress.add_task("Updating compose.yaml...", total=None)

        _update_compose_with_orchestration(runtime_config)

        progress.update(task, description="✅ compose.yaml updated")

    # Success message
    console.print("\n" + "=" * 60, style="green")
    console.print("✅ ABI Swarm added successfully!", style="green bold")
    console.print("=" * 60, style="green")

    console.print("\n📊 Created Components:", style="cyan")
    console.print(f"  • Planner Agent (A2A port {planner_port})", style="green")
    console.print(f"  • Orchestrator Agent (A2A port {orchestrator_port}, Web port {web_interface_port})", style="green")
    console.print(f"  • Builder Agent (A2A port {builder_port})", style="green")

    console.print("\n🚀 Next Steps:", style="cyan")
    console.print("  1. Start the system:", style="white")
    console.print("     abi-core run", style="blue")
    console.print("\n  2. Send queries to Orchestrator:", style="white")
    console.print(f"     curl -X POST http://localhost:{web_interface_port}/stream \\", style="blue")
    console.print('       -H "Content-Type: application/json" \\', style="blue")
    console.print('       -d \'{"query": "analyze customer data", "context_id": "test", "task_id": "task1"}\'', style="blue")
    console.print("\n  3. Or use A2A protocol:", style="white")
    console.print(f"     curl -X POST http://localhost:{orchestrator_port}/a2a/send-streaming-message \\", style="blue")
    console.print('       -H "Content-Type: application/json" \\', style="blue")
    console.print('       -d \'{"id": "req1", "params": {"message": {"role": "user", ...}}}\'', style="blue")


def _update_compose_with_orchestration(runtime_config: dict):
    """Update compose.yaml with Planner and Orchestrator services"""

    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')

    if not compose_file.exists():
        console.print("⚠️  No compose file found", style="yellow")
        return

    try:
        import yaml

        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}

        if 'services' not in compose_data:
            compose_data['services'] = {}

        # Get project name
        project_name = runtime_config.get('project', {}).get('name', Path.cwd().name)
        project_dir = project_name.lower().replace(' ', '-').replace('_', '-')

        # Get model serving mode from runtime.yaml
        provision_mode = runtime_config.get('project', {}).get('model_serving', 'centralized')

        console.print(f"[📊] Model serving mode from runtime.yaml: {provision_mode}", style="cyan")

        # Get dynamic ports from runtime config
        agents = runtime_config.get('agents', {})
        planner_port = agents.get('planner', {}).get('port', 11437)
        orchestrator_port = agents.get('orchestrator', {}).get('port', 8002)
        builder_port = agents.get('builder', {}).get('port', 11439)
        web_interface_port = 8083

        # Find available Ollama ports
        used_ports = set()
        for service in compose_data.get('services', {}).values():
            for port_mapping in service.get('ports', []):
                if isinstance(port_mapping, str) and ':' in port_mapping:
                    host_port = port_mapping.split(':')[0]
                    used_ports.add(int(host_port))

        # Also reserve the agent ports we're about to assign
        used_ports.add(planner_port)
        used_ports.add(orchestrator_port)
        used_ports.add(builder_port)
        used_ports.add(web_interface_port)

        # Assign Ollama ports dynamically
        planner_ollama_port = 11434
        while planner_ollama_port in used_ports:
            planner_ollama_port += 1
        used_ports.add(planner_ollama_port)

        orchestrator_ollama_port = 11434
        while orchestrator_ollama_port in used_ports:
            orchestrator_ollama_port += 1
        used_ports.add(orchestrator_ollama_port)

        # Find network
        existing_networks = []
        for service_config in compose_data['services'].values():
            service_networks = service_config.get('networks', [])
            if service_networks:
                existing_networks.extend(service_networks)

        network_name = existing_networks[0] if existing_networks else 'abi-network'

        # Ensure network exists
        if 'networks' not in compose_data:
            compose_data['networks'] = {}
        if network_name not in compose_data['networks']:
            compose_data['networks'][network_name] = {'driver': 'bridge'}

        # Get model configuration from runtime
        default_model = runtime_config.get('project', {}).get('default_model', 'qwen2.5:3b')
        planner_model = agents.get('planner', {}).get('model', default_model)
        orchestrator_model = agents.get('orchestrator', {}).get('model', default_model)

        # Configure Planner based on provision mode
        # Only dynamic/runtime variables in compose
        # Static variables are in Dockerfile
        planner_env = [
            f'MODEL_NAME={planner_model}',
            f'AGENT_PORT={planner_port}',
            f'SERVICE_PORT={planner_port}',
            f'MCP_HOST={project_dir}-semantic-layer',
            'MCP_PORT=10100',
            'MCP_TRANSPORT=streamable-http',
            f'SEMANTIC_LAYER_HOST=http://{project_dir}-semantic-layer:10100',
            f'GUARDIAN_URL=http://{project_dir}-guardian:11438',
            f'OPA_URL=http://{project_dir}-opa:8181'
        ]

        planner_volumes = [
            './logs:/app/logs',
            './agents/planner/agent_cards:/app/agent_cards:ro'
        ]
        planner_ports = [f'{planner_port}:{planner_port}']

        if provision_mode == 'distributed':
            planner_env.extend(['START_OLLAMA=false', 'LOAD_MODELS=false'])
            planner_ports.append(f'{planner_ollama_port}:11434')
            planner_volumes.append('ollama-planner:/root/.ollama')
        else:
            planner_env.extend([
                'START_OLLAMA=false',
                'LOAD_MODELS=false',
                'OLLAMA_HOST=http://ollama:11434'
            ])

        # Add Planner service
        compose_data['services'][f'{project_dir}-planner'] = {
            'build': './agents/planner',
            'container_name': f'{project_dir}-planner',
            'ports': planner_ports,
            'environment': planner_env,
            'volumes': planner_volumes,
            'networks': [network_name],
            'depends_on': [f'{project_dir}-semantic-layer']
        }

        # Configure Orchestrator based on provision mode
        # Only dynamic/runtime variables in compose
        # Static variables are in Dockerfile
        orchestrator_env = [
            f'MODEL_NAME={orchestrator_model}',
            f'AGENT_PORT={orchestrator_port}',
            f'SERVICE_PORT={orchestrator_port}',
            f'WEB_INTERFACE_PORT=8083',
            f'MCP_HOST={project_dir}-semantic-layer',
            'MCP_PORT=10100',
            'MCP_TRANSPORT=streamable-http',
            f'SEMANTIC_LAYER_HOST=http://{project_dir}-semantic-layer:10100',
            f'GUARDIAN_URL=http://{project_dir}-guardian:11438',
            f'OPA_URL=http://{project_dir}-opa:8181',
            f'ARTIFACT_ENDPOINT=http://{project_dir}-minio:9000',
            f'ARTIFACT_ACCESS_KEY=minioadmin',
            f'ARTIFACT_SECRET_KEY=minioadmin',
            'LOG_TO_ARTIFACT_STORE=true',
            'LOG_AGENT_NAME=orchestrator',
            'LOG_BUCKET=abi-logs',
            'EPHEMERAL_AUTO_DESTROY=true',
            f'DOCKER_NETWORK={project_dir}_abi-network',
            f'AGENT_MEMORY_URL=http://{project_dir}-agent-memory:8000',
        ]

        orchestrator_volumes = [
            './logs:/app/logs',
            './agents/orchestrator/agent_cards:/app/agent_cards:ro',
            '/var/run/docker.sock:/var/run/docker.sock',
        ]
        orchestrator_ports = [
            f'{orchestrator_port}:{orchestrator_port}',
            f'{web_interface_port}:8083'
        ]

        if provision_mode == 'distributed':
            orchestrator_env.extend(['START_OLLAMA=true', 'LOAD_MODELS=true'])
            orchestrator_ports.append(f'{orchestrator_ollama_port}:11434')
            orchestrator_volumes.append('ollama-orchestrator:/root/.ollama')
        else:
            orchestrator_env.extend([
                'START_OLLAMA=false',
                'LOAD_MODELS=false',
                'OLLAMA_HOST=http://ollama:11434'
            ])

        # Add Orchestrator service
        compose_data['services'][f'{project_dir}-orchestrator'] = {
            'build': './agents/orchestrator',
            'container_name': f'{project_dir}-orchestrator',
            'ports': orchestrator_ports,
            'environment': orchestrator_env,
            'volumes': orchestrator_volumes,
            'networks': [network_name],
            'depends_on': [f'{project_dir}-semantic-layer', f'{project_dir}-planner']
        }

        # Configure Builder
        builder_model = agents.get('builder', {}).get('model', default_model)

        builder_env = [
            f'MODEL_NAME={builder_model}',
            'EPHEMERAL_MODEL_NAME=devstral:24b',
            f'AGENT_PORT={builder_port}',
            f'SERVICE_PORT={builder_port}',
            f'MCP_HOST={project_dir}-semantic-layer',
            'MCP_PORT=10100',
            'MCP_TRANSPORT=streamable-http',
            f'SEMANTIC_LAYER_HOST=http://{project_dir}-semantic-layer:10100',
            f'GUARDIAN_URL=http://{project_dir}-guardian:11438',
            f'OPA_URL=http://{project_dir}-opa:8181',
            f'DOCKER_NETWORK={project_dir}_abi-network',
            f'ARTIFACT_ENDPOINT=http://{project_dir}-minio:9000',
            'ARTIFACT_ACCESS_KEY=minioadmin',
            'ARTIFACT_SECRET_KEY=minioadmin',
            'ARTIFACT_BUCKET=abi-artifacts',
            'LOG_TO_ARTIFACT_STORE=true',
            'LOG_AGENT_NAME=builder',
            'LOG_BUCKET=abi-logs',
            f'AGENT_MEMORY_URL=http://{project_dir}-agent-memory:8000',
        ]

        builder_volumes = [
            './logs:/app/logs',
            './agents/builder/agent_cards:/app/agent_cards:ro',
            '/var/run/docker.sock:/var/run/docker.sock',
        ]
        builder_ports = [f'{builder_port}:{builder_port}']

        if provision_mode == 'distributed':
            builder_env.extend(['START_OLLAMA=true', 'LOAD_MODELS=true'])
            builder_ollama_port = orchestrator_ollama_port + 1
            while builder_ollama_port in used_ports:
                builder_ollama_port += 1
            used_ports.add(builder_ollama_port)
            builder_ports.append(f'{builder_ollama_port}:11434')
            builder_volumes.append('ollama-builder:/root/.ollama')
        else:
            builder_env.extend([
                'START_OLLAMA=false',
                'LOAD_MODELS=false',
                'OLLAMA_HOST=http://ollama:11434'
            ])

        # Add Builder service
        compose_data['services'][f'{project_dir}-builder'] = {
            'build': './agents/builder',
            'container_name': f'{project_dir}-builder',
            'ports': builder_ports,
            'environment': builder_env,
            'volumes': builder_volumes,
            'networks': [network_name],
            'depends_on': [f'{project_dir}-semantic-layer']
        }

        # Add Redis Stack (backing store for Agent Memory Server)
        compose_data['services'][f'{project_dir}-redis-stack'] = {
            'image': 'redis:8',
            'container_name': f'{project_dir}-redis-stack',
            'ports': ['6379:6379'],
            'command': 'redis-server --appendonly yes',
            'volumes': ['redis_data:/data'],
            'networks': [network_name],
            'restart': 'unless-stopped',
            'healthcheck': {
                'test': ['CMD', 'redis-cli', 'ping'],
                'interval': '10s',
                'timeout': '5s',
                'retries': 5,
            },
        }

        # Add Agent Memory Server (working + long-term memory, shared by the swarm)
        compose_data['services'][f'{project_dir}-agent-memory'] = {
            'image': 'redislabs/agent-memory-server:latest',
            'container_name': f'{project_dir}-agent-memory',
            'ports': ['8100:8000'],
            'command': 'agent-memory api --host 0.0.0.0 --port 8000 --task-backend=asyncio',
            'environment': [
                f'REDIS_URL=redis://{project_dir}-redis-stack:6379',
                'PORT=8000',
                'DISABLE_AUTH=true',
                'LONG_TERM_MEMORY=true',
                'GENERATION_MODEL=ollama/qwen2.5:3b',
                'FAST_MODEL=ollama/qwen2.5:3b',
                'SLOW_MODEL=ollama/qwen2.5:3b',
                'EMBEDDING_MODEL=ollama/nomic-embed-text:v1.5',
                'OLLAMA_API_BASE=http://ollama:11434',
                'REDISVL_VECTOR_DIMENSIONS=768',
            ],
            'depends_on': [f'{project_dir}-redis-stack'],
            'networks': [network_name],
            'restart': 'unless-stopped',
            'healthcheck': {
                'test': ['CMD', 'curl', '-f', 'http://localhost:8000/v1/health'],
                'interval': '30s',
                'timeout': '10s',
                'retries': 3,
            },
        }
        # Builder depends on agent memory so the swarm can store/recall context
        compose_data['services'][f'{project_dir}-builder']['depends_on'].append(
            f'{project_dir}-agent-memory'
        )

        # Persist the redis volume used by the Agent Memory Server
        if 'volumes' not in compose_data:
            compose_data['volumes'] = {}
        compose_data['volumes']['redis_data'] = {'driver': 'local'}

        # Add volumes only in distributed mode
        if provision_mode == 'distributed':
            if 'volumes' not in compose_data:
                compose_data['volumes'] = {}
            compose_data['volumes']['ollama-planner'] = None
            compose_data['volumes']['ollama-orchestrator'] = None
            compose_data['volumes']['ollama-builder'] = None

        # Write updated compose file
        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)

    except Exception as e:
        console.print(f"❌ Error updating compose file: {e}", style="red")
        import traceback
        traceback.print_exc()
