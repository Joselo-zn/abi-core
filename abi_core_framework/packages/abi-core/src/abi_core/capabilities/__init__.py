"""
abi_core.capabilities — Task-centric capability matching (Phase 0: foundations).

Model a task by *what it requires* and a model by *what it provides*, over the
same 7 capability dimensions, then match them:

    from abi_core.capabilities import (
        CapabilityProfile, TaskProfile, ModelProfile,
        match_score, select_model, seed_catalog,
    )

    task = TaskProfile(capabilities=CapabilityProfile(
        code_generation=0.9, tool_usage=0.95, instruction_following=0.6,
    ))
    result = select_model(task, seed_catalog())
    result.model_name   # best-matching model
    result.gaps         # per-dimension deficits to reinforce

Foundations only: this module is pure and testable and is **not** wired into any
agent yet. The cycle (orchestrator → planner → builder → ephemeral) consumes it
in later phases. See `.abi/specs/capability-matching.md`.
"""

from abi_core.capabilities.dimensions import (
    CAPABILITY_DIMENSIONS,
    CapabilityProfile,
)
from abi_core.capabilities.profiles import (
    SOURCE_MEASURED,
    SOURCE_SEED,
    ModelProfile,
    TaskProfile,
)
from abi_core.capabilities.matching import (
    MatchResult,
    ScoredModel,
    capability_gaps,
    match_score,
    rank_models,
    select_model,
)
from abi_core.capabilities.model_profiles import (
    SEED_MODEL_PROFILES,
    get_seed_profile,
    seed_catalog,
)
from abi_core.capabilities.io import (
    SCHEMA_VERSION,
    load_catalog,
    load_profiles,
    profiles_from_document,
    profiles_to_document,
    save_profiles,
)
from abi_core.capabilities.viz import render_bars, render_radar_png
from abi_core.capabilities.stats import WilsonInterval, wilson_interval, should_stop

__all__ = [
    # dimensions
    "CAPABILITY_DIMENSIONS",
    "CapabilityProfile",
    # profiles
    "TaskProfile",
    "ModelProfile",
    "SOURCE_SEED",
    "SOURCE_MEASURED",
    # matching
    "capability_gaps",
    "match_score",
    "rank_models",
    "select_model",
    "MatchResult",
    "ScoredModel",
    # seed catalog
    "SEED_MODEL_PROFILES",
    "get_seed_profile",
    "seed_catalog",
    # io
    "SCHEMA_VERSION",
    "load_profiles",
    "load_catalog",
    "save_profiles",
    "profiles_to_document",
    "profiles_from_document",
    # viz
    "render_bars",
    "render_radar_png",
    # stats (profiling)
    "WilsonInterval",
    "wilson_interval",
    "should_stop",
]
