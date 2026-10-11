"""
Tests for the per-run project folder (abi_core.common.project_store).
Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.1-project-folder-and-full-plan.md
"""

import asyncio
import json

import pytest

from abi_core.common import project_store
from abi_core.common.plan_models import Plan, PlannerOutput


class FakeStore:
    """In-memory stand-in for ArtifactStore."""

    def __init__(self):
        self.objects, self.metadata, self.lifecycle = {}, {}, []

    async def ensure_bucket(self):
        pass

    async def ensure_expiration(self, prefix, days, rule_id):
        self.lifecycle.append((prefix, days, rule_id))

    async def upload(self, key, content, metadata=None):
        self.objects[key], self.metadata[key] = content, metadata
        return key

    async def download(self, key):
        return self.objects[key]

    async def list_artifacts(self, prefix=""):
        return [k for k in self.objects if k.startswith(prefix)]


@pytest.fixture(autouse=True)
def _reset_retention(monkeypatch):
    monkeypatch.setattr(project_store, "_retention_applied", False)


def test_project_key_layout():
    assert project_store.project_key("r1", "code", "game.py") == "projects/r1/code/game.py"
    assert project_store.project_key("r1", "spec", "game.py.tdd.json") == "projects/r1/spec/game.py.tdd.json"
    assert project_store.project_key("r1", "review/repaired", "x/game.py") == "projects/r1/review/repaired/game.py"
    with pytest.raises(ValueError):
        project_store.project_key("r1", "tdd", "game.py")  # no tdd/ area: the TDD lives in spec/
    with pytest.raises(ValueError):
        project_store.project_key("", "code", "game.py")


def test_area_for():
    assert project_store.area_for("game.py") == "code"
    assert project_store.area_for("README.md") == "docs"


def test_save_load_list_and_retention_once(monkeypatch):
    monkeypatch.setenv("PROJECT_RETENTION_DAYS", "30")
    store = FakeStore()

    async def run():
        await project_store.save_json("r1", "plan", "plan.json", {"objective": "x"}, store=store)
        await project_store.save("r1", "code", "game.py", b"print(1)", metadata={"agent": "a"}, store=store)
        await project_store.save("r1", "review", "integration-1.json", b"{}", store=store)
        await project_store.save("r1", "review/repaired", "game.py", b"print(2)", store=store)
        return (
            await project_store.load_json("r1", "plan", "plan.json", store=store),
            await project_store.list_area("r1", "review", store=store),
            await project_store.list_area("r1", "review/repaired", store=store),
        )

    plan, review, repaired = asyncio.run(run())
    assert plan == {"objective": "x"}
    assert review == ["integration-1.json"]          # review/repaired/ not mixed in
    assert repaired == ["game.py"]
    assert store.metadata["projects/r1/code/game.py"] == {"run_id": "r1", "agent": "a"}
    assert store.lifecycle == [("projects/", 30, "abi-projects-retention")]  # applied once


def test_retention_failure_does_not_block_upload():
    store = FakeStore()

    async def boom(*a):
        raise RuntimeError("lifecycle not supported")

    store.ensure_expiration = boom
    key = asyncio.run(project_store.save("r1", "code", "game.py", b"x", store=store))
    assert store.objects[key] == b"x"


def test_technical_design_kept_but_hidden_from_model_schema():
    design = {"files": [{"filename": "game.py", "role": "entry_point",
                         "responsibility": "loop", "depends_on": []}]}
    plan = Plan(objective="o", tasks=[{"task_id": "task_1", "title": "Game loop", "description": "Write the game loop in game.py"}])
    plan.technical_design = design
    out = PlannerOutput(status="ready", plan=plan).to_dict()
    # Survives parse_plan's round trip (to_dict -> model_validate -> to_dict)
    assert PlannerOutput.model_validate(out).to_dict()["plan"]["technical_design"] == design
    # ...but the model never sees it in the schema it decodes against
    assert "technical_design" not in json.dumps(PlannerOutput.model_json_schema())
