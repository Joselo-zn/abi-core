"""
abi_core.capabilities.probes — Probe model + result for capability profiling.

A ``Probe`` is a deterministically-verifiable test targeting one capability
dimension. The profiler runs it N times against a model; ``verify(output)``
returns pass/fail, and results aggregate into a ``ProbeResult`` (success ratio +
Wilson interval). See .abi/specs/capability-profiling-methodology.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from abi_core.capabilities.dimensions import CAPABILITY_DIMENSIONS
from abi_core.capabilities.stats import WilsonInterval, wilson_interval

DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Probe:
    """A single deterministically-verifiable probe for one dimension."""

    id: str
    dimension: str
    difficulty: str
    prompt: str
    verify: Callable[[str], bool]
    tools: List = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.dimension not in CAPABILITY_DIMENSIONS:
            raise ValueError(f"Unknown dimension: {self.dimension!r}")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {self.difficulty!r}")


@dataclass(frozen=True)
class ProbeResult:
    """Aggregated outcome of running a probe N times."""

    probe_id: str
    dimension: str
    difficulty: str
    successes: int
    n: int

    @property
    def ratio(self) -> float:
        return self.successes / self.n if self.n else 0.0

    @property
    def interval(self) -> WilsonInterval:
        return wilson_interval(self.successes, self.n)

    def to_dict(self) -> dict:
        ci = self.interval
        return {
            "probe_id": self.probe_id,
            "dimension": self.dimension,
            "difficulty": self.difficulty,
            "successes": self.successes,
            "n": self.n,
            "ratio": self.ratio,
            "ci_low": ci.low,
            "ci_high": ci.high,
        }
