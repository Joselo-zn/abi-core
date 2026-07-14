"""
abi_core.capabilities.matching — Compare task requirements against model capabilities.

Three operations, from finest to coarsest:

- ``capability_gaps(task, model)`` — per-dimension deficit (where task > model).
- ``match_score(task, model)``     — scalar in ``[0,1]`` to rank models.
- ``select_model(task, catalog)``  — pick the best model + report gaps.

Design choice (from the article): **excess capability does not reward**. A model
that far exceeds a requirement is not a better match — it may even be worse,
since higher raw capability tends to reduce instruction adherence. So the score
only penalizes *deficit*; it never adds credit for surplus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from abi_core.capabilities.dimensions import CAPABILITY_DIMENSIONS
from abi_core.capabilities.profiles import ModelProfile, TaskProfile


def capability_gaps(task: TaskProfile, model: ModelProfile) -> Dict[str, float]:
    """Per-dimension deficit: how much the model lacks for the task.

    Only dimensions where ``task_requirement > model_capability`` are returned
    (a model's surplus in a dimension is not a gap). Values are positive
    deficits in ``[0, 1]``.
    """
    gaps: Dict[str, float] = {}
    for dim in CAPABILITY_DIMENSIONS:
        req = task.requirement(dim)
        have = model.capability(dim)
        if req > have:
            gaps[dim] = req - have
    return gaps


def match_score(task: TaskProfile, model: ModelProfile) -> float:
    """Scalar match in ``[0,1]``: 1.0 = model covers everything the task needs.

    Weighted deficit, penalizing only what's missing:

        score = 1 - (Σ weight_d · max(0, req_d - have_d)) / (Σ weight_d)

    where the sum runs over dimensions the task actually requires
    (``req_d > 0``) and ``weight_d`` defaults to the requirement. Surplus
    capability contributes nothing (neither reward nor penalty).

    A task that requires nothing scores 1.0 for any model.
    """
    total_weight = 0.0
    penalty = 0.0
    for dim in CAPABILITY_DIMENSIONS:
        req = task.requirement(dim)
        if req <= 0.0:
            continue  # task doesn't require this dimension
        w = task.weight(dim)
        if w <= 0.0:
            continue
        deficit = max(0.0, req - model.capability(dim))
        penalty += w * deficit
        total_weight += w
    if total_weight == 0.0:
        return 1.0
    return max(0.0, 1.0 - penalty / total_weight)


@dataclass(frozen=True)
class MatchResult:
    """Outcome of selecting a model for a task."""

    model: Optional[ModelProfile]
    score: float
    gaps: Dict[str, float]
    ranked: List["ScoredModel"]

    @property
    def model_name(self) -> str:
        return self.model.model if self.model is not None else ""


@dataclass(frozen=True)
class ScoredModel:
    """A model paired with its match score (for the full ranking)."""

    model: ModelProfile
    score: float


def rank_models(task: TaskProfile, catalog: Iterable[ModelProfile]) -> List[ScoredModel]:
    """Rank all candidate models by match score (descending).

    Ties are broken deterministically by model name (secondary ascending sort),
    so equal scores always produce a stable, reproducible order.
    """
    scored = [ScoredModel(m, match_score(task, m)) for m in catalog]
    scored.sort(key=lambda sm: (-sm.score, sm.model.model))
    return scored


def select_model(
    task: TaskProfile,
    catalog: Iterable[ModelProfile],
    *,
    min_score: float = 0.0,
) -> MatchResult:
    """Pick the best-matching model for a task.

    Args:
        task: The task's capability requirements.
        catalog: Available models with their capability profiles.
        min_score: If the best score is below this threshold, ``model`` is still
            returned (the best available) but callers can inspect ``score`` to
            decide whether a reinforcement architecture is needed instead of
            trusting the model alone.

    Returns:
        A :class:`MatchResult` with the chosen model, its score, its per-dimension
        gaps, and the full ranking. If the catalog is empty, ``model`` is ``None``
        and ``score`` is ``0.0``.
    """
    ranked = rank_models(task, catalog)
    if not ranked:
        return MatchResult(model=None, score=0.0, gaps=dict(task.capabilities.to_dict()), ranked=[])

    best = ranked[0]
    gaps = capability_gaps(task, best.model)
    return MatchResult(model=best.model, score=best.score, gaps=gaps, ranked=ranked)
