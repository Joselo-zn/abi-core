"""
Task-decomposition methodology registry — framework-level, available to any
ABI-Core agent (not a Planner-only concern).

Kept as a registry (name -> guidance) rather than inline strings scattered in
prompts, so it's a single source of truth any agent can query.
"""

METHODOLOGIES: dict[str, str] = {
    "WBS": (
        "Work Breakdown Structure: hierarchical decomposition into "
        "independent, atomic deliverables (one file per task). Best for "
        "multi-file/multi-component builds."
    ),
    "SMART": (
        "Specific/Measurable/Achievable/Relevant/Time-bound framing: each "
        "task states a concrete, verifiable outcome. Best for a single "
        "well-defined deliverable with clear acceptance criteria."
    ),
    "GTD": (
        "Getting Things Done: next-actions framing, strict sequential "
        "dependency chain. Best for ordered, pipeline-style workflows."
    ),
    "Polya": (
        "How to Solve It (Polya): understand -> devise a plan -> execute -> "
        "verify. Best for open-ended, exploratory, or algorithmic problems."
    ),
}

DEFAULT_METHODOLOGY = "WBS"


def list_methodologies() -> dict[str, str]:
    """Registry of decomposition methodologies available in the framework."""
    return dict(METHODOLOGIES)
