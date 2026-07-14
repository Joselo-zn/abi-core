"""
abi_core.capabilities.io — Load / save model capability profiles as JSON.

Model profiling happens at **dev time**: the CLI profiles candidate models and
exports a JSON catalog; the agentic system loads it at deploy time and refines it
at runtime. This module is the load/save half — pure and independent of *how* the
scores were produced (seed, measured, or hand-authored).

File format (versioned so it can evolve):

    {
      "schema_version": 1,
      "generated_at": 1780000000.0,
      "generator": "abi-core capabilities profile",   # optional, provenance
      "models": [
        {
          "model": "qwen2.5:3b",
          "capabilities": {"code_generation": 0.5, ... all 7 dims ...},
          "source": "measured",
          "samples": 30,
          "updated_at": 1780000000.0,
          "metadata": {...}
        },
        ...
      ]
    }

Loading is lenient: unknown top-level keys are ignored, missing capability
dimensions default to 0.0, and each model round-trips through
``ModelProfile.from_dict`` so validation/clamping is consistent with the rest of
the package.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Union

from abi_core.capabilities.profiles import ModelProfile

SCHEMA_VERSION = 1

_PathLike = Union[str, Path]


def profiles_to_document(
    profiles: Iterable[ModelProfile],
    *,
    generator: str = "",
) -> Dict:
    """Build the serializable catalog document from model profiles."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.time(),
        "generator": generator,
        "models": [p.to_dict() for p in profiles],
    }


def profiles_from_document(document: Dict) -> List[ModelProfile]:
    """Parse a catalog document into a list of ``ModelProfile``.

    Raises:
        ValueError: if the document is not a dict or ``models`` is not a list, or
            a model entry is missing the required ``model`` name.
    """
    if not isinstance(document, dict):
        raise ValueError("Profile document must be a JSON object")

    version = document.get("schema_version")
    if version is not None and version > SCHEMA_VERSION:
        # Forward-compatible read: warn via exception detail rather than silently
        # misreading a newer schema.
        raise ValueError(
            f"Profile document schema_version={version} is newer than supported "
            f"({SCHEMA_VERSION}). Upgrade abi-core to read it."
        )

    models = document.get("models", [])
    if not isinstance(models, list):
        raise ValueError("'models' must be a list")

    result: List[ModelProfile] = []
    for entry in models:
        if not isinstance(entry, dict) or "model" not in entry:
            raise ValueError("Each model entry must be an object with a 'model' name")
        result.append(ModelProfile.from_dict(entry))
    return result


def save_profiles(
    profiles: Iterable[ModelProfile],
    path: _PathLike,
    *,
    generator: str = "",
) -> None:
    """Write model profiles to a JSON file (creates parent dirs if needed)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    document = profiles_to_document(profiles, generator=generator)
    p.write_text(json.dumps(document, indent=2), encoding="utf-8")


def load_profiles(path: _PathLike) -> List[ModelProfile]:
    """Read model profiles from a JSON file.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        ValueError: if the file is not valid JSON or not a valid profile document.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile file not found: {p}")
    try:
        document = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in profile file {p}: {e}") from e
    return profiles_from_document(document)


def load_catalog(path: _PathLike) -> Dict[str, ModelProfile]:
    """Load profiles and return them as a ``{model_name: ModelProfile}`` dict."""
    return {p.model: p for p in load_profiles(path)}
