"""
Project store — one folder per plan run in the artifact store.

Everything a run produces lives under ``projects/<run_id>/``, so a run can be
read back as a whole instead of rebuilt from per-ephemeral prefixes:

    projects/<run_id>/
      plan/plan.json              the plan as the Planner sent it (technical design inside)
      spec/<file>.tdd.json        each code agent's spec: its TDD, written before its code
      docs/<file>                 delivered documentation (README, ...)
      code/<file>.py              each code agent's code
      review/                     integration review reports, sandbox audit
      review/repaired/<file>      code rewritten by the reviewer

This module is the only place that knows the layout; callers never build
these keys by hand. The ``projects/`` prefix expires after
``PROJECT_RETENTION_DAYS`` (default 30) through a bucket lifecycle rule.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.1-project-folder-and-full-plan.md
"""

import json
import os
from typing import Any, Dict, List, Optional

from abi_core.common.artifact_store import ArtifactStore
from abi_core.common.utils import abi_logging

PROJECTS_PREFIX = "projects"
AREAS = ("plan", "spec", "docs", "code", "review", "review/repaired")
_RETENTION_RULE_ID = "abi-projects-retention"

# Once per process: the rule is bucket-wide, re-applying it on every upload
# would only repeat the same call.
_retention_applied = False


def project_key(run_id: str, area: str, filename: str) -> str:
    """Storage key of ``filename`` in ``area`` of the run's project folder."""
    if not run_id:
        raise ValueError("run_id is required")
    if area not in AREAS:
        raise ValueError(f"unknown project area {area!r} (expected one of {AREAS})")
    return f"{PROJECTS_PREFIX}/{run_id}/{area}/{os.path.basename(filename)}"


def area_for(filename: str) -> str:
    """Where a code agent's deliverable goes: .py is code, anything else docs."""
    return "code" if filename.endswith(".py") else "docs"


async def _ensure_retention(store: ArtifactStore) -> None:
    global _retention_applied
    if _retention_applied:
        return
    _retention_applied = True
    days = int(os.getenv("PROJECT_RETENTION_DAYS", "30"))
    try:
        await store.ensure_expiration(f"{PROJECTS_PREFIX}/", days, _RETENTION_RULE_ID)
    except Exception as e:
        # Non-blocking: a store without lifecycle support (or without the
        # permission) still gets the files; only the cleanup is missing.
        abi_logging(f"[⚠️] Could not set {days}-day expiration on {PROJECTS_PREFIX}/: {e}", level="warning")


async def save(
    run_id: str, area: str, filename: str, content: bytes,
    metadata: Optional[Dict[str, str]] = None, store: Optional[ArtifactStore] = None,
) -> str:
    """Upload bytes to the run's project folder. Returns the key."""
    store = store or ArtifactStore()
    key = project_key(run_id, area, filename)
    await store.ensure_bucket()
    await _ensure_retention(store)
    await store.upload(key, content, metadata={"run_id": run_id, **(metadata or {})})
    return key


async def save_json(
    run_id: str, area: str, filename: str, data: Any,
    metadata: Optional[Dict[str, str]] = None, store: Optional[ArtifactStore] = None,
) -> str:
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return await save(run_id, area, filename, content, metadata=metadata, store=store)


async def load(run_id: str, area: str, filename: str, store: Optional[ArtifactStore] = None) -> bytes:
    return await (store or ArtifactStore()).download(project_key(run_id, area, filename))


async def load_json(run_id: str, area: str, filename: str, store: Optional[ArtifactStore] = None) -> Any:
    return json.loads((await load(run_id, area, filename, store=store)).decode("utf-8"))


async def list_area(run_id: str, area: str, store: Optional[ArtifactStore] = None) -> List[str]:
    """Filenames directly in ``area`` (``review`` does not list ``review/repaired``)."""
    prefix = project_key(run_id, area, "x")[:-1]
    keys = await (store or ArtifactStore()).list_artifacts(prefix)
    return [k[len(prefix):] for k in keys if "/" not in k[len(prefix):]]
