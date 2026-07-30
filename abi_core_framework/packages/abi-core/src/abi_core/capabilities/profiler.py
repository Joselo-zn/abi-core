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


# ── v2: operational-envelope profiling (staircase with confirmation) ──

from typing import Dict as _Dict, List as _List  # noqa: E402

from abi_core.capabilities.probes import LeveledProbe, MAX_LEVEL, envelope_score  # noqa: E402
from abi_core.capabilities.stats import wilson_interval  # noqa: E402

# A level is "passed" when the success ratio clears PASS_RATIO *and* the Wilson
# lower bound clears CI_FLOOR — so passing is statistically backed, not luck.
DEFAULT_PASS_RATIO = 0.8
DEFAULT_CI_FLOOR = 0.6


def run_level(
    probes: _List[LeveledProbe],
    run_fn: RunFn,
    *,
    reps: int,
) -> tuple:
    """Run all probes of a level ``reps`` times each; return (successes, n)."""
    successes = 0
    n = 0
    for probe in probes:
        for _ in range(reps):
            n += 1
            try:
                if probe.verify(run_fn(probe.prompt, probe.tools)):
                    successes += 1
            except Exception:
                pass
    return successes, n


def level_passed(
    successes: int,
    n: int,
    *,
    pass_ratio: float = DEFAULT_PASS_RATIO,
    ci_floor: float = DEFAULT_CI_FLOOR,
) -> bool:
    """A level is passed if ratio >= pass_ratio and Wilson lower bound >= ci_floor."""
    if n == 0:
        return False
    ratio = successes / n
    if ratio < pass_ratio:
        return False
    return wilson_interval(successes, n).low >= ci_floor


def profile_dimension_envelope(
    levels: _Dict[int, _List[LeveledProbe]],
    run_fn: RunFn,
    *,
    reps: int = 10,
    max_level: int = MAX_LEVEL,
    pass_ratio: float = DEFAULT_PASS_RATIO,
    ci_floor: float = DEFAULT_CI_FLOOR,
) -> _Dict:
    """Climb complexity levels until a confirmed break; return the envelope.

    Staircase with confirmation (spec §3): on a level failure, retry once before
    declaring the break, to avoid a false negative from a noisy model.

    Args:
        levels: ``{level_number: [LeveledProbe, ...]}`` for one dimension.
        run_fn: ``(prompt, tools) -> output`` driving the model.
        reps: repetitions per probe at each level.

    Returns:
        Dict with ``highest_reliable_level``, ``score`` (envelope, [0,1]), and
        ``per_level`` diagnostics.
    """
    highest = 0
    per_level = []
    ordered = sorted(l for l in levels if levels[l])

    for level in ordered:
        if level > max_level:
            break
        probes = levels[level]
        succ, n = run_level(probes, run_fn, reps=reps)
        passed = level_passed(succ, n, pass_ratio=pass_ratio, ci_floor=ci_floor)

        if not passed:
            # Confirm the break: retry once before giving up (avoid false negative).
            succ2, n2 = run_level(probes, run_fn, reps=reps)
            if level_passed(succ2, n2, pass_ratio=pass_ratio, ci_floor=ci_floor):
                succ, n, passed = succ + succ2, n + n2, True
            else:
                per_level.append({"level": level, "successes": succ, "n": n, "passed": False})
                break

        highest = level
        per_level.append({"level": level, "successes": succ, "n": n, "passed": True})

    return {
        "highest_reliable_level": highest,
        "score": envelope_score(highest, max_level),
        "per_level": per_level,
    }


def profile_model_envelope(
    model: str,
    leveled_by_dim: _Dict[str, _Dict[int, _List[LeveledProbe]]],
    run_fn: RunFn,
    *,
    reps: int = 10,
    max_level: int = MAX_LEVEL,
    pass_ratio: float = DEFAULT_PASS_RATIO,
    ci_floor: float = DEFAULT_CI_FLOOR,
    metadata: _Dict | None = None,
) -> ModelProfile:
    """Profile a model as operational envelopes across leveled dimensions (v2).

    Runs the staircase per dimension; each dimension's score is its envelope
    (highest reliable level / max_level). Dimensions without a leveled battery
    are left at 0.0 and noted in metadata as unmeasured.

    Args:
        model: Model name/tag.
        leveled_by_dim: ``{dimension: {level: [LeveledProbe]}}``.
        run_fn: ``(prompt, tools) -> output`` driving the model.

    Returns:
        A measured ``ModelProfile`` (envelope semantics) with per-dimension
        diagnostics in ``metadata``.
    """
    scores: _Dict[str, float] = {}
    envelopes: _Dict[str, dict] = {}
    total_runs = 0

    for dim, levels in leveled_by_dim.items():
        result = profile_dimension_envelope(
            levels, run_fn, reps=reps, max_level=max_level,
            pass_ratio=pass_ratio, ci_floor=ci_floor,
        )
        scores[dim] = result["score"]
        envelopes[dim] = result
        total_runs += sum(pl["n"] for pl in result["per_level"])

    meta = dict(metadata or {})
    meta["envelopes"] = envelopes
    meta["scoring"] = "operational_envelope_v2"
    meta["unmeasured_dimensions"] = [
        d for d in CAPABILITY_DIMENSIONS if d not in leveled_by_dim
    ]

    return ModelProfile(
        model=model,
        capabilities=CapabilityProfile.from_dict(scores),
        source=SOURCE_MEASURED,
        samples=total_runs,
        metadata=meta,
    )