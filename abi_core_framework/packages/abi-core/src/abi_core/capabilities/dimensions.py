"""
abi_core.capabilities.dimensions — The 7 capability dimensions and the profile vector.

A **capability profile** is a vector of 7 scores in ``[0.0, 1.0]``. The same
dimensions describe both what a *task* requires and what a *model* provides, so
the two are directly comparable (``Task Profile ↔ Capability Profile``).

The dimensions come from the article
*Challenges and Agent Behavior in Collaborative Swarm Environments*:
capability, not model popularity, should drive selection. The 7th dimension,
``instruction_following``, is central to the thesis — as raw capability grows,
models tend to optimize for the *inferred* objective rather than strict
instruction compliance, so adherence is its own axis, orthogonal to reasoning.

Capabilities are **cognitive**. Operational constraints (latency, cost, memory
footprint) are deliberately *not* dimensions here — mixing "it's fast" with
"it can generate code" pollutes the match. Constraints are a separate axis,
applied as a later filter, not inside this vector.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Dict, Tuple

# Canonical order of the 7 dimensions. Anything iterating dimensions should use
# this tuple so ordering is stable across the codebase.
CAPABILITY_DIMENSIONS: Tuple[str, ...] = (
    "code_generation",       # produce correct, complete code
    "tool_usage",            # reliably invoke tools / emit tool_calls
    "reasoning",             # logic, inference, problem solving
    "planning",              # decompose and sequence sub-tasks
    "structured_output",     # emit strict formats (JSON/schema)
    "context_span",          # stay coherent over long context
    "instruction_following", # adhere to instructions vs. optimizing for inferred goal
)


def _clamp(value: float) -> float:
    """Clamp a score into the valid ``[0.0, 1.0]`` range."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


@dataclass(frozen=True)
class CapabilityProfile:
    """A vector of 7 capability scores in ``[0.0, 1.0]``.

    Shared base for task requirements and model capabilities. Immutable so a
    profile can be safely shared, cached, and used as a stable reference.

    Values are clamped to ``[0, 1]`` on construction, so callers don't have to
    pre-validate derived or measured scores.
    """

    code_generation: float = 0.0
    tool_usage: float = 0.0
    reasoning: float = 0.0
    planning: float = 0.0
    structured_output: float = 0.0
    context_span: float = 0.0
    instruction_following: float = 0.0

    def __post_init__(self) -> None:
        # frozen=True blocks normal assignment; use object.__setattr__ to clamp.
        for f in fields(self):
            object.__setattr__(self, f.name, _clamp(getattr(self, f.name)))

    def get(self, dimension: str) -> float:
        """Return the score for ``dimension`` (KeyError if unknown)."""
        if dimension not in CAPABILITY_DIMENSIONS:
            raise KeyError(f"Unknown capability dimension: {dimension!r}")
        return getattr(self, dimension)

    def to_dict(self) -> Dict[str, float]:
        """Return the profile as an ordered ``{dimension: score}`` dict."""
        return {dim: getattr(self, dim) for dim in CAPABILITY_DIMENSIONS}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "CapabilityProfile":
        """Build a profile from a dict; unknown keys are ignored, missing = 0.0."""
        return cls(**{dim: float(data[dim]) for dim in CAPABILITY_DIMENSIONS if dim in data})
