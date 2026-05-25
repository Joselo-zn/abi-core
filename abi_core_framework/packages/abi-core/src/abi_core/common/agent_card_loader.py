"""
Agent Card Loader — separates A2A protocol card from ABI metadata.

a2a-sdk 1.0 uses protobuf AgentCard that only accepts protocol fields.
ABI agent cards on disk contain extra metadata (auth, llmConfig, supportedTasks, etc.)
that must be separated before constructing the protocol object.
"""

import json
from pathlib import Path
from typing import Tuple

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentInterface


def load_agent_card(path: str) -> Tuple[AgentCard, dict]:
    """Load agent card JSON — returns (protocol_card, abi_metadata).

    Args:
        path: Path to agent card JSON file.

    Returns:
        Tuple of (AgentCard protobuf object, dict with ABI-specific metadata).

    Raises:
        FileNotFoundError: If card file doesn't exist.
        json.JSONDecodeError: If card file is invalid JSON.
    """
    card_path = Path(path)
    if not card_path.exists():
        raise FileNotFoundError(f"Agent card not found: {path}")

    with card_path.open() as f:
        full_data = json.load(f)

    return build_agent_card(full_data)


def build_agent_card(full_data: dict) -> Tuple[AgentCard, dict]:
    """Build AgentCard from a full data dict (including ABI metadata).

    Args:
        full_data: Complete agent card dict (as stored on disk).

    Returns:
        Tuple of (AgentCard protobuf object, dict with ABI-specific metadata).
    """
    # Build skills
    skills = []
    for s in full_data.get("skills", []):
        skills.append(AgentSkill(
            id=s.get("id", ""),
            name=s.get("name", ""),
            description=s.get("description", ""),
            tags=s.get("tags", []),
            examples=s.get("examples", []),
            input_modes=s.get("inputModes", []),
            output_modes=s.get("outputModes", []),
        ))

    # Build capabilities
    caps_data = full_data.get("capabilities", {})
    capabilities = AgentCapabilities(
        streaming=_to_bool(caps_data.get("streaming", False)),
        push_notifications=_to_bool(caps_data.get("pushNotifications", False)),
    )

    # Build supported_interfaces from url field or supportedInterfaces (MessageToDict format)
    url = full_data.get("url", "")
    if not url:
        interfaces_data = full_data.get("supportedInterfaces", [])
        if interfaces_data and isinstance(interfaces_data, list):
            url = interfaces_data[0].get("url", "")
    interfaces = [AgentInterface(url=url, protocol_binding="JSONRPC")] if url else []

    # Construct protocol card
    card = AgentCard(
        name=full_data.get("name", ""),
        description=full_data.get("description", ""),
        version=full_data.get("version", "1.0.0"),
        capabilities=capabilities,
        default_input_modes=full_data.get("defaultInputModes", ["text/plain"]),
        default_output_modes=full_data.get("defaultOutputModes", ["text/plain"]),
        supported_interfaces=interfaces,
        skills=skills,
    )

    # ABI metadata (not part of A2A protocol)
    abi_meta = {
        "id": full_data.get("id"),
        "auth": full_data.get("auth"),
        "supportedTasks": full_data.get("supportedTasks"),
        "llmConfig": full_data.get("llmConfig"),
        "url": url,
        "metadata": full_data.get("metadata"),
    }

    return card, abi_meta


def get_agent_url(card: AgentCard) -> str:
    """Extract URL from AgentCard (protocol object).

    Args:
        card: AgentCard protobuf object.

    Returns:
        URL string, or empty string if no interfaces defined.
    """
    if card.supported_interfaces:
        return card.supported_interfaces[0].url
    return ""


def _to_bool(value) -> bool:
    """Convert string/bool to bool. Handles 'True'/'False' strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)
