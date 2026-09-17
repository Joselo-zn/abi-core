"""
`ui` — run a UI client shipped inside abi_core (no per-project generated code).
"""

import importlib.util
import os
import subprocess

import click

from .utils import console


def _chainlit_app_path() -> str:
    spec = importlib.util.find_spec("abi_core.ui.chainlit_app")
    if spec is None or not spec.origin:
        raise click.ClickException(
            "abi_core.ui.chainlit_app not found — install the 'ui' extra: "
            "pip install \"abi-core-ai[ui]\""
        )
    return spec.origin


@click.group()
def ui():
    """Run a chat UI client shipped inside abi-core."""
    pass


@ui.command("chainlit")
@click.option('--url', required=True, help='Target agent /stream URL, e.g. http://localhost:8083')
@click.option('--title', default='ABI', help='UI title shown in the chat')
@click.option('--port', default=8000, type=int, help='Port to serve the UI on')
@click.option('--headless', is_flag=True, help="Don't auto-open a browser window")
def ui_chainlit(url, title, port, headless):
    """Run the ABI Chainlit chat UI against an agent.

    Runs abi_core.ui.chainlit_app — the single canonical implementation —
    instead of a per-project copy. Both `abi-core add chainlit`'s generated
    Docker service and standalone scripts should use this instead of
    invoking `chainlit run app.py` directly.
    """
    app_path = _chainlit_app_path()

    env = os.environ.copy()
    env["ABI_AGENT_URL"] = url
    env["ABI_UI_TITLE"] = title

    cmd = ["chainlit", "run", app_path, "--host", "0.0.0.0", "--port", str(port)]
    if headless:
        cmd.append("--headless")

    console.print(f"🐝 Starting Chainlit UI on port {port} → {url}", style="blue")
    try:
        subprocess.run(cmd, env=env, check=True)
    except FileNotFoundError:
        raise click.ClickException(
            "chainlit is not installed — install the 'ui' extra: pip install \"abi-core-ai[ui]\""
        )
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"chainlit exited with an error: {e}")
    except KeyboardInterrupt:
        console.print("\n🛑 Stopped.", style="yellow")
