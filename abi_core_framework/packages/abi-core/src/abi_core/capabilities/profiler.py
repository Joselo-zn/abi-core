"""
abi_core.capabilities.profiler — Run probes N times and aggregate into a profile.

The runner is transport-agnostic: it takes a ``run_fn(prompt, tools) -> str`` so
it can drive any model (Ollama, OpenAI, a stub in tests). It repeats each probe
with the adaptive Wilson stopping rule, aggregates per-dimension scores
(difficulty-weighted), and builds a measured ``ModelProfile``.

See .abi/specs/capability-profiling-methodology.md.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List

from abi_core.capabilities.dimensions import CAPABILITY_DIMENSIONS, CapabilityProfile
from abi_core.capabilities.probes import Probe, ProbeResult
from abi_core.capabilities.profiles import SOURCE_MEASURED, ModelProfile
from abi_core.capabilities.stats import (
    DEFAULT_CI_WIDTH,
    DEFAULT_N_MAX,
    DEFAULT_N_MIN,
    should_stop,
)

RunFn = Callable[[str, list], str]

# Difficulty weights for aggregating probe ratios into a dimension score.
_DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 2.0, "hard": 3.0}


def run_probe(
    probe: Probe,
    run_fn: RunFn,
    *,
    n_min: int = DEFAULT_N_MIN,
    n_max: int = DEFAULT_N_MAX,
    ci_width: float = DEFAULT_CI_WIDTH,
) -> ProbeResult:
    """Run one probe repeatedly until the adaptive stopping rule fires."""
    successes = 0
    n = 0
    while True:
        output = run_fn(probe.prompt, probe.tools)
        n += 1
        try:
            if probe.verify(output):
                successes += 1
        except Exception:
            pass  # a verifier crash counts as failure
        if should_stop(successes, n, n_min=n_min, n_max=n_max, ci_width=ci_width):
            break
    return ProbeResult(
        probe_id=probe.id,
        dimension=probe.dimension,
        difficulty=probe.difficulty,
        successes=successes,
        n=n,
    )


def aggregate_dimension(results: Iterable[ProbeResult]) -> float:
    """Difficulty-weighted mean of probe ratios for one dimension."""
    total_w = 0.0
    acc = 0.0
    for r in results:
        w = _DIFFICULTY_WEIGHT.get(r.difficulty, 1.0)
        acc += w * r.ratio
        total_w += w
    return acc / total_w if total_w else 0.0


def profile_model(
    model: str,
    probes: List[Probe],
    run_fn: RunFn,
    *,
    n_min: int = DEFAULT_N_MIN,
    n_max: int = DEFAULT_N_MAX,
    ci_width: float = DEFAULT_CI_WIDTH,
    metadata: Dict | None = None,
) -> ModelProfile:
    """Run a probe battery against a model and build a measured ModelProfile.

    Args:
        model: Model name/tag.
        probes: The probe battery (multiple probes per dimension).
        run_fn: ``(prompt, tools) -> output`` — drives the model under test.
        metadata: Extra provenance stored on the profile (probe_suite_version,
            temperature, hardware, ...).

    Returns:
        A ``ModelProfile`` with ``source="measured"`` and per-probe results plus
        per-dimension intervals recorded in ``metadata``.
    """
    by_dim: Dict[str, List[ProbeResult]] = {d: [] for d in CAPABILITY_DIMENSIONS}
    all_results: List[ProbeResult] = []

    for probe in probes:
        res = run_probe(probe, run_fn, n_min=n_min, n_max=n_max, ci_width=ci_width)
        by_dim[res.dimension].append(res)
        all_results.append(res)

    scores = {d: aggregate_dimension(by_dim[d]) for d in CAPABILITY_DIMENSIONS if by_dim[d]}
    total_samples = sum(r.n for r in all_results)

    meta = dict(metadata or {})
    meta["probe_results"] = [r.to_dict() for r in all_results]

    return ModelProfile(
        model=model,
        capabilities=CapabilityProfile.from_dict(scores),
        source=SOURCE_MEASURED,
        samples=total_samples,
        metadata=meta,
    )
