"""
Agent Card Initialization
Completes agent cards with authentication fields at runtime
"""

import json
import secrets
from pathlib import Path
from typing import Dict, Any


def generate_agent_auth(agent_name: str) -> Dict[str, Any]:
    """Generate authentication credentials for an agent"""
    agent_id = f"agent://{agent_name.lower().replace(' ', '_')}"
    key_id = f"{agent_id}-default"
    shared_secret = secrets.token_urlsafe(32)
    
    return {
        "id": agent_id,
        "auth": {
            "method": "hmac_sha256",
            "key_id": key_id,
            "shared_secret": shared_secret
        }
    }


def complete_agent_card(card_path: str | Path) -> bool:
    """
    Complete an agent card with missing authentication fields
    
    Args:
        card_path: Path to the agent card JSON file
        
    Returns:
        bool: True if card was updated, False if already complete
    """
    card_path = Path(card_path)
    
    if not card_path.exists():
        raise FileNotFoundError(f"Agent card not found: {card_path}")
    
    # Load existing card
    with open(card_path, 'r') as f:
        card = json.load(f)
    
    # Check if already has required fields
    if 'id' in card and 'auth' in card:
        return False  # Already complete
    
    # Get agent name
    agent_name = card.get('name', 'unknown_agent')
    
    # Generate auth fields
    auth_data = generate_agent_auth(agent_name)
    
    # Add missing fields
    if 'id' not in card:
        card['id'] = auth_data['id']
    
    if 'auth' not in card:
        card['auth'] = auth_data['auth']
    
    # Add @context if missing
    if '@context' not in card:
        card['@context'] = [
            "https://raw.githubusercontent.com/GoogleCloudPlatform/a2a-llm/main/a2a/ontology/a2a_context.jsonld"
        ]
    
    # Add @type if missing
    if '@type' not in card:
        card['@type'] = "Agent"
    
    # Write updated card
    with open(card_path, 'w') as f:
        json.dump(card, f, indent=2)
    
    return True


async def register_agent_card_with_semantic_layer(card_path: str | Path) -> bool:
    """
    Register the agent card with the semantic layer
    
    Args:
        card_path: Path to the agent card JSON file
        
    Returns:
        bool: True if registration successful
    """
    import os
    from abi_core.common.utils import get_mcp_server_config
    from abi_core.abi_mcp import client
    
    try:
        # Load the completed card
        with open(card_path, 'r') as f:
            card_data = json.load(f)
        
        # Get MCP config
        config = get_mcp_server_config()
        
        # Register with semantic layer
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            # Build context for registration
            context = {
                "agent_id": card_data.get('id'),
                "key_id": card_data.get('auth', {}).get('key_id'),
                "shared_secret": card_data.get('auth', {}).get('shared_secret')
            }
            
            result = await client.register_agent(session, card_data, context)
            
            if result and hasattr(result, 'content'):
                if isinstance(result.content, list) and result.content:
                    response = json.loads(result.content[0].text)
                    if response.get('success'):
                        print(f"[✅] Agent registered with semantic layer: {card_data.get('name')}")
                        return True
            
            print(f"[⚠️] Failed to register agent with semantic layer")
            return False
            
    except Exception as e:
        print(f"[⚠️] Could not register with semantic layer: {e}")
        return False


def init_agent_card_on_startup(card_path: str | Path) -> None:
    """
    Initialize agent card on container startup
    Should be called from main.py before starting the agent
    
    Args:
        card_path: Path to the agent card JSON file
    """
    try:
        updated = complete_agent_card(card_path)
        if updated:
            print(f"[✅] Agent card completed with authentication fields: {card_path}")
        else:
            print(f"[ℹ️] Agent card already complete: {card_path}")
    except Exception as e:
        print(f"[⚠️] Warning: Could not complete agent card: {e}")
        # Don't fail startup, just warn


async def init_and_register_agent_card(card_path: str | Path) -> None:
    """
    Complete agent card and register with semantic layer
    
    Args:
        card_path: Path to the agent card JSON file
    """
    # First, complete the card with auth fields
    init_agent_card_on_startup(card_path)
    
    # Then, register with semantic layer
    await register_agent_card_with_semantic_layer(card_path)
