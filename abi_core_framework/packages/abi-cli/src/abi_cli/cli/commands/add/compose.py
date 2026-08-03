"""
Docker Compose editing helpers shared across `add` sub-commands.

Note: `_update_compose_with_agent` used to be defined twice in the old
monolithic add.py (module-level name collision — the second definition
silently shadowed the first, which never ran). This module keeps only the
version that was actually executing.
"""

from pathlib import Path

from ..utils import console


def _update_compose_with_agent(context: dict):
    """Update compose.yaml with new agent service"""

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
        agent_name = context['agent_name']
        agent_port = context['agent_port']
        web_port = context.get('web_interface_port')
        with_web = context.get('with_web_interface', False)

        # Get model serving mode from runtime.yaml
        runtime_file = Path('.abi/runtime.yaml')
        provision_mode = 'distributed'  # default

        if runtime_file.exists():
            try:
                runtime_data = yaml.safe_load(runtime_file.read_text())
                provision_mode = runtime_data.get('project', {}).get('model_serving', 'distributed')
            except Exception as e:
                console.print(f"Warning: Could not read model_serving from runtime.yaml: {e}", style="yellow")

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

        # Only dynamic variables in compose (static ones are in Dockerfile)
        agent_env = [
            f'AGENT_PORT={agent_port}',
            f'SERVICE_PORT={agent_port}',
        ]

        if with_web:
            agent_env.append(f'WEB_INTERFACE_PORT={web_port}')

        # Get project name for consistent naming
        project_name = Path.cwd().name.lower().replace(' ', '-').replace('_', '-')

        # Add MCP connection if semantic layer exists
        if any('semantic' in svc for svc in compose_data['services'].keys()):
            agent_env.extend([
                f'MCP_HOST={project_name}-semantic-layer',
                'MCP_PORT=10100',
                'MCP_TRANSPORT=streamable-http',
                f'SEMANTIC_LAYER_HOST=http://{project_name}-semantic-layer:10100'
            ])

        # Add Guardian and OPA URLs if they exist
        if any('guardian' in svc for svc in compose_data['services'].keys()):
            agent_env.extend([
                f'GUARDIAN_URL=http://{project_name}-guardian:11438',
                f'OPA_URL=http://{project_name}-opa:8181'
            ])

        # Add Agent Memory (short/long-term memory API) if that service exists
        if any('agent-memory' in svc for svc in compose_data['services'].keys()):
            agent_env.append(f'AGENT_MEMORY_URL=http://{project_name}-agent-memory:8000')

        agent_volumes = [
            './logs:/app/logs',
            f'./agents/{agent_name}/agent_cards:/app/agent_cards:ro'
        ]
        agent_ports = [f'{agent_port}:{agent_port}']

        if with_web:
            agent_ports.append(f'{web_port}:{web_port}')

        # Configure based on provision mode
        if provision_mode == 'distributed':
            agent_env.extend(['START_OLLAMA=false', 'LOAD_MODELS=false'])
            agent_volumes.append(f'ollama-{agent_name}:/root/.ollama')
        else:
            agent_env.extend([
                'START_OLLAMA=false',
                'LOAD_MODELS=false',
                'OLLAMA_HOST=http://ollama:11434'
            ])

        # Use consistent naming: {project_name}-{agent_name}
        service_name = f'{project_name}-{agent_name}'

        # Add agent service with depends_on
        agent_service = {
            'build': f'./agents/{agent_name}',
            'container_name': service_name,
            'ports': agent_ports,
            'environment': agent_env,
            'volumes': agent_volumes,
            'networks': [network_name],
            'depends_on': []
        }

        # Add dependencies
        if provision_mode == 'centralized':
            if 'ollama' in compose_data['services']:
                agent_service['depends_on'].append('ollama')

        if any('semantic' in svc for svc in compose_data['services'].keys()):
            semantic_service = f'{project_name}-semantic-layer'
            if semantic_service in compose_data['services']:
                agent_service['depends_on'].append(semantic_service)

        if any('agent-memory' in svc for svc in compose_data['services'].keys()):
            memory_service = f'{project_name}-agent-memory'
            if memory_service in compose_data['services']:
                agent_service['depends_on'].append(memory_service)

        # Remove depends_on if empty
        if not agent_service['depends_on']:
            del agent_service['depends_on']

        compose_data['services'][service_name] = agent_service

        # Add volume only in distributed mode
        if provision_mode == 'distributed':
            if 'volumes' not in compose_data:
                compose_data['volumes'] = {}
            compose_data['volumes'][f'ollama-{agent_name}'] = None

        # Write updated compose file
        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)

        console.print(f"[✅] Compose updated with {agent_name} agent ({provision_mode} mode)", style="green")

    except Exception as e:
        console.print(f"⚠️  Error updating compose file: {e}", style="yellow")


def _update_compose_with_service(compose_file, service_name, service_type, service_port, context):
    """Update docker-compose.yml to include new service with port conflict detection"""
    import yaml

    try:
        # Read current compose file
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}

        services = compose_data.get('services', {})

        # Reuse whatever network the project's existing services are already
        # on (e.g. 'abi-network') instead of inventing a new one, so this
        # service can actually reach — and be reached by — the rest of them.
        existing_networks = []
        for svc_config in services.values():
            existing_networks.extend(svc_config.get('networks', []) or [])
        network_name = existing_networks[0] if existing_networks else 'abi-network'

        # Check if service already exists (try different naming patterns)
        service_key = service_name.replace('_', '-')
        project_name = context.get('project_name', Path.cwd().name)
        project_service_key = f"{project_name}-{service_key}"

        if service_key in services or project_service_key in services:
            return  # Already exists

        # Use project-prefixed service name for consistency with template
        final_service_key = project_service_key

        # Find available port to avoid conflicts
        used_ports = set()
        for svc_name, svc_config in services.items():
            ports = svc_config.get('ports', [])
            for port_mapping in ports:
                if isinstance(port_mapping, str) and ':' in port_mapping:
                    external_port = int(port_mapping.split(':')[0])
                    used_ports.add(external_port)

        # Find next available port starting from the requested port
        available_port = service_port
        while available_port in used_ports:
            available_port += 1

        # Generate service definition based on type
        if service_type == 'semantic-layer':
            service_definition = {
                'build': f'./services/{service_name}',
                'container_name': f'{project_name}-{service_key}',
                'ports': [f'{available_port}:{available_port}'],
                'environment': [
                    'ABI_ROLE=Semantic Layer',
                    'ABI_NODE=ABI Node',
                    'AGENT_CARDS_BASE=/app/agent_cards',
                    f'ABI_LLM_BASE=http://{project_name}-guardian:11438',
                    'EMBEDDING_MODEL=nomic-embed-text:v1.5',
                    f'GUARDIAN_URL=http://{project_name}-guardian:11438',
                    f'OPA_URL=http://{project_name}-opa:8181',
                    'SEMANTIC_LAYER_HOST=0.0.0.0',
                    f'SEMANTIC_LAYER_PORT={available_port}'
                ],
                'volumes': [f'./services/{service_name}/agent_cards:/app/agent_cards:ro', f'./services/{service_name}/tool_cards:/app/tool_cards:ro', './logs:/app/logs'],
                'networks': [network_name],
                'depends_on': []
            }
        elif service_type == 'guardian':
            service_definition = {
                'build': f'./services/{service_name}',
                'container_name': f'{project_name}-{service_key}',
                'ports': [f'{available_port}:{available_port}'],
                'environment': [
                    'ABI_ROLE=Guardian Service',
                    'ABI_NODE=ABI Node',
                    f'OPA_URL=http://{project_name}-opa:8181',
                    'GUARDIAN_PORT=' + str(available_port),
                    # Entrypoint variables for Ollama (embeddings)
                    'START_OLLAMA=false',
                    'LOAD_MODELS=false',
                    'SERVICE_MODULE=main',
                    f'SERVICE_PORT={available_port}'
                ],
                'volumes': ['./logs:/app/logs'],
                'networks': [network_name],
                'depends_on': []
            }
        elif service_type == 'guardian-native':
            service_definition = {
                'build': f'./services/{service_name}',
                'container_name': f'{project_name}-{service_key}',
                'ports': [f'{available_port}:{available_port}'],
                'environment': [
                    f'OPA_URL=http://{project_name}-opa:8181',
                    'GUARDIAN_PORT=' + str(available_port),
                    'AGENT_CARDS_BASE=/app/agent_cards',
                    'OLLAMA_HOST=http://ollama:11434'
                ],
                'volumes': [
                    './agent_cards:/app/agent_cards:ro',
                    './logs:/app/logs'
                ],
                'networks': [network_name],
                'depends_on': ['ollama'] if 'ollama' in services else []
            }
        elif service_type == 'mcp-api':
            service_definition = {
                'build': f'./services/{service_name}',
                'container_name': f'{project_name}-{service_key}',
                'ports': [f'{available_port}:{available_port}'],
                'environment': [
                    'MCP_API_HOST=0.0.0.0',
                    f'MCP_API_PORT={available_port}',
                    f'SEMANTIC_LAYER_HOST=http://{project_name}-semantic-layer:10100'
                ],
                'volumes': ['./logs:/app/logs'],
                'networks': [network_name],
                'depends_on': []
            }
        else:
            # Generic service
            service_definition = {
                'build': f'./services/{service_name}',
                'container_name': f'{project_name}-{service_key}',
                'ports': [f'{available_port}:{available_port}'],
                'volumes': ['./logs:/app/logs'],
                'networks': [network_name]
            }

        # Add service to compose data
        services[final_service_key] = service_definition
        compose_data['services'] = services

        # Ensure the (reused, not invented) network is declared
        if 'networks' not in compose_data:
            compose_data['networks'] = {}
        compose_data['networks'].setdefault(network_name, {'driver': 'bridge'})

        # Write updated compose file
        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)

        # Show port information
        if available_port != service_port:
            console.print(f"⚠️  Port {service_port} was in use, assigned port {available_port} instead", style="yellow")

        console.print(f"✅ Updated {compose_file.name} with {service_name} service on port {available_port}", style="green")

    except Exception as e:
        console.print(f"⚠️  Warning: Could not update {compose_file.name}: {e}", style="yellow")


def _update_compose_with_semantic_layer(compose_file, context):
    """Update docker-compose.yml to include semantic layer service (legacy function)"""
    _update_compose_with_service(compose_file, 'semantic_layer', 'semantic-layer', 10100, context)


def _update_compose_with_agent_card(agent_name: str, agent_card_filename: str):
    """Update docker-compose to add AGENT_CARD environment variable to agent service"""
    import yaml

    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')

    if not compose_file.exists():
        return

    try:
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}

        if 'services' not in compose_data:
            return

        # Find the agent service (try different naming patterns)
        project_name = Path.cwd().name.lower().replace(' ', '-').replace('_', '-')
        possible_service_names = [
            f'{project_name}-{agent_name}',
            f'{agent_name}-agent',
            agent_name
        ]

        service_name = None
        for name in possible_service_names:
            if name in compose_data['services']:
                service_name = name
                break

        if not service_name:
            return

        # Add AGENT_CARD environment variable
        service = compose_data['services'][service_name]
        if 'environment' not in service:
            service['environment'] = []

        # Check if AGENT_CARD already exists
        env_list = service['environment']
        agent_card_var = f'AGENT_CARD=./agent_cards/{agent_card_filename}'

        # Remove old AGENT_CARD if exists
        env_list = [e for e in env_list if not (isinstance(e, str) and e.startswith('AGENT_CARD='))]

        # Add new AGENT_CARD
        env_list.append(agent_card_var)
        service['environment'] = env_list

        # Add volume mount for agent_cards if not exists
        if 'volumes' not in service:
            service['volumes'] = []

        agent_cards_volume = f'./agents/{agent_name}/agent_cards:/app/agent_cards:ro'
        if agent_cards_volume not in service['volumes']:
            service['volumes'].append(agent_cards_volume)

        # Write updated compose file
        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)

    except Exception as e:
        console.print(f"⚠️  Could not update compose with agent card: {e}", style="yellow")


def _build_agent_memory_services(project_dir: str, network_name: str) -> dict:
    """Return the {redis-stack, agent-memory} compose service definitions.

    Single source of truth reused by both `add service agent-memory`
    (standalone) and `add abi-swarm` (which needs the same infra as part of
    its orchestration bundle) — previously these were duplicated inline in
    abi_swarm.py.
    """
    return {
        f'{project_dir}-redis-stack': {
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
        },
        f'{project_dir}-agent-memory': {
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
        },
    }


def _update_compose_with_agent_memory(compose_file, runtime_config: dict):
    """Add the Agent Memory Server + Redis to compose.yaml, and retroactively
    wire AGENT_MEMORY_URL (+ depends_on) into every agent already registered
    in runtime.yaml.

    This is what lets a plain `add agent` (no swarm) start using
    abi_core.memory.add_short_term_memory/get_short_term_memory — that API
    silently no-ops without a reachable AGENT_MEMORY_URL, so an existing
    agent that predates this service needs the retroactive wiring, not just
    agents created afterward (those already get it via `_update_compose_with_agent`).
    """
    import yaml

    try:
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f) or {}

        if 'services' not in compose_data:
            compose_data['services'] = {}
        services = compose_data['services']

        project_dir = Path.cwd().name.lower().replace(' ', '-').replace('_', '-')

        if any('agent-memory' in svc for svc in services.keys()):
            console.print("❌ Agent Memory service already exists!", style="red")
            return False

        # Find network (reuse whatever the project already uses)
        existing_networks = []
        for service_config in services.values():
            existing_networks.extend(service_config.get('networks', []) or [])
        network_name = existing_networks[0] if existing_networks else 'abi-network'
        if 'networks' not in compose_data:
            compose_data['networks'] = {}
        compose_data['networks'].setdefault(network_name, {'driver': 'bridge'})

        # Avoid host-port conflicts (container ports stay fixed; only the
        # host-side mapping shifts if 6379/8100 are already taken).
        used_ports = set()
        for svc_config in services.values():
            for port_mapping in svc_config.get('ports', []):
                if isinstance(port_mapping, str) and ':' in port_mapping:
                    used_ports.add(int(port_mapping.split(':')[0]))

        new_services = _build_agent_memory_services(project_dir, network_name)

        redis_port = 6379
        while redis_port in used_ports:
            redis_port += 1
        if redis_port != 6379:
            new_services[f'{project_dir}-redis-stack']['ports'] = [f'{redis_port}:6379']
        used_ports.add(redis_port)

        memory_port = 8100
        while memory_port in used_ports:
            memory_port += 1
        if memory_port != 8100:
            new_services[f'{project_dir}-agent-memory']['ports'] = [f'{memory_port}:8000']

        services.update(new_services)

        if 'volumes' not in compose_data:
            compose_data['volumes'] = {}
        compose_data['volumes'].setdefault('redis_data', {'driver': 'local'})

        # Retroactively wire AGENT_MEMORY_URL + depends_on into every agent
        # already registered in runtime.yaml (agents added going forward
        # pick this up automatically via _update_compose_with_agent).
        memory_url = f'AGENT_MEMORY_URL=http://{project_dir}-agent-memory:8000'
        memory_service_name = f'{project_dir}-agent-memory'
        wired = []
        for agent_name in runtime_config.get('agents', {}).keys():
            possible_names = [f'{project_dir}-{agent_name}', f'{agent_name}-agent', agent_name]
            svc_key = next((n for n in possible_names if n in services), None)
            if not svc_key or svc_key in new_services:
                continue
            svc = services[svc_key]
            env_list = svc.setdefault('environment', [])
            if not any(isinstance(e, str) and e.startswith('AGENT_MEMORY_URL=') for e in env_list):
                env_list.append(memory_url)
            depends = svc.setdefault('depends_on', [])
            if memory_service_name not in depends:
                depends.append(memory_service_name)
            wired.append(svc_key)

        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)

        console.print("✅ Agent Memory Server (AMS) + Redis added", style="green")
        if wired:
            console.print(f"🔗 Wired AGENT_MEMORY_URL into existing agents: {', '.join(wired)}", style="green")
        return True

    except Exception as e:
        console.print(f"⚠️  Error updating compose file: {e}", style="yellow")
        return False
