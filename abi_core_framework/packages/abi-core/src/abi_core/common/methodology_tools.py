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


async def select_methodology(
    query: str,
    llm_config: dict,
    *,
    session_id: str | None = None,
    system_prompt: str | None = None,
) -> dict:
    """Ask the LLM to pick a decomposition methodology for `query`.

    Framework-level, available to any ABI-Core agent — extracted verbatim
    from what was `AbiPlannerAgent._select_methodology` (Planner-only
    before 2026-08-03), now parameterized by `llm_config` instead of
    reading a module-level config so any agent's task/step can call it.

    A dedicated LLM call, meant to run BEFORE the actual decomposition so
    its guidance can shape that prompt. Best-effort: any failure (LLM
    error, unparseable response, name outside the registry) falls back to
    DEFAULT_METHODOLOGY.

    Returns {"methodology": str, "rationale": str}.
    """
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.prompts import build_methodology_selection_prompt
    from abi_core.common.utils import abi_logging, clean_llm_json

    try:
        text = await invoke(
            llm_config,
            build_methodology_selection_prompt(query),
            thread_id=session_id,
            system_prompt=system_prompt,
        )
        parsed = clean_llm_json(text)
        methodology = parsed.get("methodology", DEFAULT_METHODOLOGY)
        if methodology not in METHODOLOGIES:
            abi_logging(f"[⚠️] Unknown methodology '{methodology}', defaulting to {DEFAULT_METHODOLOGY}")
            methodology = DEFAULT_METHODOLOGY
        rationale = parsed.get("rationale", "")
        abi_logging(f"[🧭] Methodology selected: {methodology} — {rationale}")
        return {"methodology": methodology, "rationale": rationale}
    except Exception as e:  # noqa: BLE001 — best-effort, never block decomposition
        abi_logging(f"[⚠️] Methodology selection failed, defaulting to {DEFAULT_METHODOLOGY}: {e}")
        return {"methodology": DEFAULT_METHODOLOGY, "rationale": "Default: safest for atomic task constraints."}
