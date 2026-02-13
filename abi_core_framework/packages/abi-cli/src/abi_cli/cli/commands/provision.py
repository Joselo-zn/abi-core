"""
Provision models command for ABI-Core CLI
"""
import click
import subprocess
import yaml
from pathlib import Path
from .utils import render_template_content


@click.command('provision-models')
@click.option('--force', is_flag=True, help='Force re-download even if models exist')
def provision_models(force):
    """Provision LLM and embedding models for the project
    
    This command will:
    - Start required Ollama services
    - Download LLM models
    - Download embedding models
    - Update runtime.yaml with provisioning status
    
    The behavior depends on model_serving mode (centralized/distributed).
    """
    
    # Verify we're in an ABI project
    runtime_file = Path('.abi/runtime.yaml')
    if not runtime_file.exists():
        click.echo("❌ Not in an ABI project directory")
        click.echo("💡 Run this command from your project root")
        return 1
    
    # Read runtime configuration
    try:
        with open(runtime_file, 'r') as f:
            runtime_config = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"❌ Error reading runtime.yaml: {e}")
        return 1
    
    project_name = runtime_config.get('project', {}).get('name', 'unknown')
    model_serving = runtime_config.get('project', {}).get('model_serving', 'distributed')
    agents = runtime_config.get('agents', {})
    
    click.echo(f"🚀 Provisioning models for {project_name}")
    click.echo(f"📊 Mode: {model_serving}")
    click.echo("")
    
    # Check if docker-compose exists
    compose_file = Path('compose.yaml')
    if not compose_file.exists():
        compose_file = Path('docker-compose.yml')
        if not compose_file.exists():
            click.echo("❌ No compose.yaml or docker-compose.yml found")
            return 1
    
    # Render and execute model-loader script
    try:
        # Prepare context for script
        context = {
            'project_name': project_name,
            'project_dir': project_name.lower().replace(' ', '_').replace('-', '_'),
            'model_name': runtime_config.get('project', {}).get('default_model', 'qwen2.5:3b'),
            'embedding_model': 'nomic-embed-text:v1.5',
            'model_serving': model_serving,
            'agents': agents
        }
        
        # Render script
        script_content = render_template_content('project/scripts/model-loader.sh', context)
        
        # Save to temporary file
        script_path = Path('.abi/model-loader.sh')
        script_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        script_path.chmod(0o755)
        
        # Execute script
        click.echo("📦 Starting model provisioning...")
        click.echo("")
        
        result = subprocess.run(
            ['bash', str(script_path)],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            click.echo("")
            click.echo("✅ Models provisioned successfully!")
            
            # Update runtime.yaml with provisioning status
            if 'models' not in runtime_config:
                runtime_config['models'] = {}
            
            runtime_config['models']['llm'] = {
                'name': context['model_name'],
                'provisioned': True
            }
            runtime_config['models']['embedding'] = {
                'name': context['embedding_model'],
                'provisioned': True
            }
            
            with open(runtime_file, 'w') as f:
                yaml.dump(runtime_config, f, default_flow_style=False, sort_keys=False)
            
            click.echo("📝 Updated runtime.yaml with provisioning status")
            return 0
        else:
            click.echo("")
            click.echo("❌ Model provisioning failed")
            return result.returncode
            
    except Exception as e:
        click.echo(f"❌ Error during provisioning: {e}")
        return 1
