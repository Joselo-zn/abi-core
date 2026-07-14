"""
abi_core.capabilities.profiles — Task and model profiles built on CapabilityProfile.

- ``TaskProfile``  — what a task *requires* (+ optional per-dimension weights).
- ``ModelProfile`` — what a model *provides* (+ provenance: seed vs measured).

Both wrap a :class:`~abi_core.capabilities.dimensions.CapabilityProfile` so they
share the same 7-dimension vector and are directly comparable by the matching
functions.

A ``TaskProfile`` is *system state that crosses agent hops*: the Planner derives
it and the Builder/ephemeral consume it. It carries in the ``builder_spec`` /
system memory — it is not re-inferred at each hop (avoids inter-agent context
degradation; see WORKING_RULES → "Perspectiva Local vs Global").
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from abi_core.capabilities.dimensions import CAPABILITY_DIMENSIONS, CapabilityProfile


@dataclass(frozen=True)
class TaskProfile:
    """What a task requires, as a capability vector plus optional weights.

    ``weights`` lets a task say a dimension matters more than its raw
    requirement suggests. When a dimension has no weight, matching defaults its
    weight to the requirement itself (a dimension the task doesn't ask for
    neither counts nor penalizes).
    """

    capabilities: CapabilityProfile = field(default_factory=CapabilityProfile)
    weights: Dict[str, float] = field(default_factory=dict)
    # Optional provenance / debugging aids (not used by matching).
    task_id: str = ""
    source: str = ""  # e.g. "heuristic", "llm", "manual"

    def requirement(self, dimension: str) -> float:
        """Required score for ``dimension``."""
        return self.capabilities.get(dimension)

    def weight(self, dimension: str) -> float:
        """Weight for ``dimension``; defaults to the requirement itself."""
        return float(self.weights.get(dimension, self.capabilities.get(dimension)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities": self.capabilities.to_dict(),
            "weights": dict(self.weights),
            "task_id": self.task_id,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskProfile":
        caps = data.get("capabilities", {})
        return cls(
            capabilities=CapabilityProfile.from_dict(caps) if isinstance(caps, dict) else CapabilityProfile(),
            weights={k: float(v) for k, v in (data.get("weights") or {}).items()},
            task_id=data.get("task_id", ""),
            source=data.get("source", ""),
        )


# Provenance markers for a model's capability scores.
SOURCE_SEED = "seed"          # initial, qualitative estimate (honest guess)
SOURCE_MEASURED = "measured"  # refined from observed executions


@dataclass(frozen=True)
class ModelProfile:
    """What a model provides, as a capability vector plus provenance.

    ``source`` distinguishes a hand-set seed from measured scores, and
    ``samples`` tracks how many executions informed the current values — so the
    system can refine a profile over time (moving average) without losing track
    of whether a number was guessed or observed.
    """

    model: str
    capabilities: CapabilityProfile = field(default_factory=CapabilityProfile)
    source: str = SOURCE_SEED
    samples: int = 0
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def capability(self, dimension: str) -> float:
        """Provided score for ``dimension``."""
        return self.capabilities.get(dimension)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "capabilities": self.capabilities.to_dict(),
            "source": self.source,
            "samples": self.samples,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelProfile":
        caps = data.get("capabilities", {})
        return cls(
            model=data["model"],
            capabilities=CapabilityProfile.from_dict(caps) if isinstance(caps, dict) else CapabilityProfile(),
            source=data.get("source", SOURCE_SEED),
            samples=int(data.get("samples", 0)),
            updated_at=float(data.get("updated_at", time.time())),
            metadata=dict(data.get("metadata", {})),
        )

    def with_observation(
        self,
        dimension: str,
        observed: float,
    ) -> "ModelProfile":
        """Return a new profile with ``dimension`` refined by one observation.

        Uses an incremental running mean over ``samples`` so an early seed
        smoothly gives way to measured data. Marks the profile as ``measured``.
        This is the hook Plan Learning uses to update profiles from executions;
        Phase 0 ships it but does not wire automatic updates yet.
        """
        observed = max(0.0, min(1.0, float(observed)))
        n = self.samples
        current = self.capabilities.get(dimension)
        # Incremental mean: new_avg = avg + (x - avg) / (n + 1)
        new_value = current + (observed - current) / (n + 1)
        new_caps = CapabilityProfile.from_dict({**self.capabilities.to_dict(), dimension: new_value})
        return ModelProfile(
            model=self.model,
            capabilities=new_caps,
            source=SOURCE_MEASURED,
            samples=n + 1,
            updated_at=time.time(),
            metadata=dict(self.metadata),
        )
