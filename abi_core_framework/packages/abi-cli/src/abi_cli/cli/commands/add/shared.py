"""
Cross-domain helpers shared by multiple `add` sub-commands (and by create.py).
"""

from pathlib import Path
from secrets import token_urlsafe

from ..utils import console


def _generate_agent_card(name, description, model, url, tasks):
    """Generate agent card JSON structure based on planner template"""
    import uuid
    from datetime import datetime

    # Generate unique agent ID
    agent_id = f"agent://{name.lower().replace(' ', '_').replace('-', '_')}"

    # Create skills from tasks
    skills = []
    for i, task in enumerate(tasks):
        skill_id = task.lower().replace(' ', '_').replace('-', '_')
        skill_name = task.replace('_', ' ').title()

        skills.append({
            "id": skill_id,
            "name": skill_name,
            "description": f"{skill_name} functionality for {name}",
            "tags": [task.lower(), "processing", "analysis"],
            "examples": [f"Execute {task.lower()} operation"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"]
        })

    auth = {
        "method": "hmac_sha256",
        "key_id": f"{agent_id}-default",
        "shared_secret": token_urlsafe(32),  # random, persistente en la card
    }

    # Generate agent card structure
    agent_card = {
        "@context": [
            "https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"
        ],
        "@type": "Agent",
        "id": agent_id,
        "name": name,
        "description": description,
        "url": url,
        "version": "1.0.0",
        "capabilities": {
            "streaming": "True",
            "pushNotifications": "True",
            "stateTransitionHistory": "False"
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "supportedTasks": tasks,
        "llmConfig": {
            "provider": "ollama",
            "model": model,
            "temperature": 0.1
        },
        "tools": [],
        "functions": [],
        "embedding": False,
        "prompt": (
            f"You are {name}, a specialized agent responsible for "
            f"{description.lower()}. Process user requests efficiently and "
            f"provide clear, structured responses."
        ),
        "skills": skills,
        "auth": auth,
        "metadata": {
            "created": datetime.utcnow().isoformat(),
            "generator": "abi-core-cli",
            "version": "1.0.0"
        }
    }

    return agent_card


def _get_next_available_port(start_port=8000):
    """Get next available port starting from start_port"""
    import yaml

    used_ports = set()

    # Check docker-compose.yml for used ports
    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')

    if compose_file.exists():
        try:
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)

            services = compose_data.get('services', {})
            for service_name, service_config in services.items():
                ports = service_config.get('ports', [])
                for port_mapping in ports:
                    if isinstance(port_mapping, str):
                        external_port = int(port_mapping.split(':')[0])
                        used_ports.add(external_port)
        except Exception as e:
            console.print(f"Warning: Could not parse compose file: {e}", style="yellow")

    # Find next available port
    current_port = start_port
    while current_port in used_ports:
        current_port += 1

    return current_port
