"""
`add chainlit` — scaffold a Chainlit chat UI as a Docker service.
"""

import click
from pathlib import Path

from ..utils import console, update_runtime_config, render_template_content
from .shared import _get_next_available_port


def _detect_web_agent(project_dir: str):
    """Find an agent with a web interface from .abi/runtime.yaml.

    Returns (service_url, display_name) where service_url is the in-Docker URL
    (``http://<project>-<agent>:<web_port>``). Prefers the orchestrator; falls
    back to the first agent that has a ``web_interface_port``. Returns
    (None, None) if none is found.
    """
    import yaml as _yaml

    runtime_file = Path('.abi/runtime.yaml')
    if not runtime_file.exists():
        return None, None
    try:
        runtime = _yaml.safe_load(runtime_file.read_text()) or {}
    except Exception:
        return None, None

    agents = runtime.get('agents', {}) or {}
    candidates = {
        key: cfg for key, cfg in agents.items()
        if cfg.get('web_interface_port')
    }
    if not candidates:
        return None, None

    # Prefer orchestrator
    key = next((k for k in candidates if 'orchestrator' in k.lower()), None)
    key = key or next(iter(candidates))
    cfg = candidates[key]
    agent_slug = key.replace('_', '-')
    port = cfg.get('web_interface_port')
    return f"http://{project_dir}-{agent_slug}:{port}", cfg.get('name', key)


@click.command("chainlit")
@click.option('--url', help='Target agent /stream URL (Docker service name). Default: auto-detected from .abi', default=None)
@click.option('--title', help='UI title shown in the chat', default=None)
@click.option('--dir', 'ui_dir', help='Directory to generate the UI in', default='ui')
def add_chainlit(url, title, ui_dir):
    """Add a Chainlit chat UI as a Docker service (started by 'abi-core run').

    The UI is a thin SSE client — it opens a framework-managed session (so
    multi-turn stays coherent) and streams status/result updates. If --url is
    omitted, the target agent is auto-detected from .abi/runtime.yaml (the
    agent with a web interface). Runs containerized in the project's network.
    """
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    target = Path(ui_dir)
    if target.exists():
        console.print(f"❌ Directory '{ui_dir}' already exists.", style="red")
        console.print("💡 Choose another with --dir, or remove it first.", style="yellow")
        return

    # Project slug drives Docker service names — read it from runtime.yaml
    # (source of truth), falling back to the directory name.
    project_name = Path.cwd().name
    try:
        import yaml as _yaml
        _rt = _yaml.safe_load(Path('.abi/runtime.yaml').read_text()) or {}
        project_name = _rt.get('project', {}).get('name', project_name)
    except Exception:
        pass
    project_dir = project_name.lower().replace(' ', '-').replace('_', '-')
    ui_title = title or f"{project_name} Chat"

    # Resolve the target agent URL (Docker service name), auto-detecting if needed.
    if not url:
        url, agent_display = _detect_web_agent(project_dir)
        if not url:
            console.print("❌ No agent with a web interface found in .abi/runtime.yaml.", style="red")
            console.print("💡 Add one with 'abi-core add agent <name> --with-web-interface',", style="yellow")
            console.print("   or pass --url http://<project>-<agent>:<port> explicitly.", style="yellow")
            return
        console.print(f"🔎 Auto-detected agent: {agent_display} → {url}", style="dim")

    # Dynamic host port for the UI (don't collide with existing services).
    ui_host_port = _get_next_available_port(8500)

    context = {
        'project_name': project_name,
        'ui_title': ui_title,
        'agent_url': url,
    }

    files = [
        ('ui/app.py', 'app.py'),
        ('ui/config.py', 'config.py'),
        ('ui/requirements.txt', 'requirements.txt'),
        ('ui/chainlit.md', 'chainlit.md'),
        ('ui/Dockerfile', 'Dockerfile'),
        ('ui/.chainlit/config.toml', '.chainlit/config.toml'),
    ]

    (target / '.chainlit').mkdir(parents=True)
    for template_name, out_rel in files:
        content = render_template_content(template_name, context)
        out_path = target / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            f.write(content)

    # Register as a Docker service so 'abi-core run' starts it.
    _update_compose_with_chainlit(project_dir, url, ui_host_port, ui_dir)

    # Track in runtime.yaml
    update_runtime_config('services', {
        'chainlit_ui': {
            'name': ui_title,
            'type': 'chainlit-ui',
            'port': ui_host_port,
            'agent_url': url,
            'path': str(target),
            'enabled': True,
        }
    })

    console.print(f"\n✅ Chainlit UI added as a service!", style="green")
    console.print(f"📁 Location: {target}", style="blue")
    console.print(f"🔗 Talks to: {url}", style="blue")
    console.print(f"🌐 UI will be at: http://localhost:{ui_host_port}", style="blue")
    console.print("\n📋 Next step:", style="yellow")
    console.print("  abi-core run    # builds and starts the UI with the rest of the stack", style="dim")


def _update_compose_with_chainlit(project_dir: str, agent_url: str, host_port: int, ui_dir: str):
    """Add the Chainlit UI as a service in compose.yaml."""
    import yaml

    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')
    if not compose_file.exists():
        console.print("⚠️  No compose file found — generated the UI files only.", style="yellow")
        return

    try:
        with open(compose_file) as f:
            compose_data = yaml.safe_load(f) or {}
        compose_data.setdefault('services', {})

        # Reuse the project's network
        existing_networks = []
        for svc in compose_data['services'].values():
            existing_networks.extend(svc.get('networks', []) or [])
        network_name = existing_networks[0] if existing_networks else 'abi-network'
        compose_data.setdefault('networks', {})
        compose_data['networks'].setdefault(network_name, {'driver': 'bridge'})

        service_name = f'{project_dir}-chatui'
        compose_data['services'][service_name] = {
            'build': f'./{ui_dir}',
            'container_name': service_name,
            'ports': [f'{host_port}:8000'],
            'environment': [f'ABI_AGENT_URL={agent_url}'],
            'networks': [network_name],
        }

        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)
        console.print(f"[✅] Compose updated with {service_name} (host port {host_port})", style="green")
    except Exception as e:
        console.print(f"⚠️  Could not update compose file: {e}", style="yellow")
