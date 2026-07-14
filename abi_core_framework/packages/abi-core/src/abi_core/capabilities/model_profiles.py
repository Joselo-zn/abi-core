"""
abi_core.capabilities.model_profiles — Seed catalog of model capability profiles.

These are **seeds**: honest qualitative estimates (``source="seed"``,
``samples=0``), not measurements. They come from observed behavior in the swarm
(e.g. ``devstral:24b`` generates strong code but rarely emits tool_calls;
smaller ``qwen2.5`` models follow instructions more reliably). They exist so the
system can start matching *today*; measured executions refine them over time
(``ModelProfile.with_observation`` → Plan Learning).

The thesis in one row: a large model can have high ``reasoning``/``code_generation``
yet low ``instruction_following`` — which is exactly why a small model can be the
better orchestrator. The seeds encode that pattern rather than "bigger = better".

Deployments can override or extend this catalog (a given node only has certain
models pulled). Phase 0 exposes the seed + a lookup; config/env override and
Redis-backed learning come in later phases.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from abi_core.capabilities.dimensions import CapabilityProfile
from abi_core.capabilities.profiles import SOURCE_SEED, ModelProfile


def _seed(model: str, **scores: float) -> ModelProfile:
    return ModelProfile(
        model=model,
        capabilities=CapabilityProfile(**scores),
        source=SOURCE_SEED,
        samples=0,
    )


# Seed catalog. Scores are estimates in [0,1]; refine by measurement.
SEED_MODEL_PROFILES: Dict[str, ModelProfile] = {
    # Large coder: excellent code, weak at obeying the tool_calls contract.
    "devstral:24b": _seed(
        "devstral:24b",
        code_generation=0.90,
        tool_usage=0.30,
        reasoning=0.70,
        planning=0.50,
        structured_output=0.85,
        context_span=0.80,
        instruction_following=0.35,
    ),
    # Large general model: strong reasoning, still loose on strict compliance.
    "dolphin:70b": _seed(
        "dolphin:70b",
        code_generation=0.75,
        tool_usage=0.35,
        reasoning=0.85,
        planning=0.70,
        structured_output=0.70,
        context_span=0.85,
        instruction_following=0.40,
    ),
    # Small, obedient model: modest raw capability, high adherence — a good
    # orchestrator/planner despite being small.
    "qwen2.5:3b": _seed(
        "qwen2.5:3b",
        code_generation=0.50,
        tool_usage=0.60,
        reasoning=0.45,
        planning=0.60,
        structured_output=0.70,
        context_span=0.40,
        instruction_following=0.75,
    ),
    # Even smaller: lower capability across the board, still fairly obedient.
    "qwen2.5:1.5b": _seed(
        "qwen2.5:1.5b",
        code_generation=0.35,
        tool_usage=0.50,
        reasoning=0.35,
        planning=0.45,
        structured_output=0.60,
        context_span=0.30,
        instruction_following=0.70,
    ),
}


def get_seed_profile(model: str) -> Optional[ModelProfile]:
    """Return the seed profile for ``model``, or ``None`` if not in the catalog."""
    return SEED_MODEL_PROFILES.get(model)


def seed_catalog(models: Optional[List[str]] = None) -> List[ModelProfile]:
    """Return seed profiles as a list, optionally filtered to ``models``.

    Args:
        models: If given, only profiles for these model names are returned
            (unknown names are skipped). If ``None``, the whole seed catalog is
            returned. Use this to reflect the models actually pulled on a node.

    Returns:
        A list of :class:`ModelProfile`.
    """
    if models is None:
        return list(SEED_MODEL_PROFILES.values())
    return [SEED_MODEL_PROFILES[m] for m in models if m in SEED_MODEL_PROFILES]
