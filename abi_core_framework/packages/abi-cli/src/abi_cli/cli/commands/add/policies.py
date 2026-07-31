"""
`add policies` — scaffold a custom Rego policy set.
"""

import click
from pathlib import Path
from rich.prompt import Prompt

from ..utils import console, update_runtime_config


@click.command("policies")
@click.option('--name', '-n', required=True, help='Policy set name')
@click.option('--domain', help='Domain for policies')
def add_policies(name, domain):
    """Add custom security policies"""

    # Check if we're in an ABI project
    if not Path('.abi').exists():
        console.print("❌ Not in an ABI project directory. Run 'abi-core create project' first.", style="red")
        return

    if not domain:
        domain = Prompt.ask("Policy domain", default="custom")

    policies_dir = Path('policies')
    policies_dir.mkdir(exist_ok=True)

    policy_file = policies_dir / f"{name.lower().replace(' ', '_').replace('-', '_')}.rego"

    if policy_file.exists():
        console.print(f"❌ Policy '{name}' already exists", style="red")
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        task = progress.add_task("Creating custom policies...", total=None)

        # Generate basic policy file
        policy_content = f'''# {name} Custom Policies
# Domain: {domain}

package {name.lower().replace(' ', '_').replace('-', '_')}.custom

# Import ABI core policies
import data.abi.core

# Custom rules for {domain} domain
domain := "{domain}"

# Allow basic operations
allow if {{
    input.action in ["read", "query"]
    input.domain == domain
}}

# Deny dangerous operations
deny contains "Dangerous operation blocked" if {{
    input.action in ["delete", "destroy"]
}}
'''

        with open(policy_file, 'w') as f:
            f.write(policy_content)

        # Update runtime configuration
        update_runtime_config('policies', {
            name.lower().replace(' ', '_').replace('-', '_'): {
                'name': name,
                'domain': domain,
                'file': str(policy_file)
            }
        })

        progress.update(task, description="Policies created successfully!", completed=True)

    console.print(f"\n✅ Policies '{name}' added successfully!", style="green")
    console.print(f"📁 Location: {policy_file}", style="blue")
