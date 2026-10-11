"""
Tests for abi_core.ui.run_follow's decision logic: finding a run that is
still going when a conversation is resumed, the counter a resumed page
shows, diffing what the page already has, and the cross-replica stop mark.
"""

import json
from datetime import datetime, timedelta, timezone

from abi_core.ui.run_follow import (
    STOP_KEY,
    diff_items,
    find_active_run,
    interrupted_name,
    is_still_running,
    running_name,
    stop_requested,
)

NOW = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


def _run_step(state="running", beat_ago=2, end=None, label="Diseñando el plan", start_ago=83, as_json=False):
    marker = {"state": state, "label": label}
    if beat_ago is not None:
        marker["heartbeat_at"] = (NOW - timedelta(seconds=beat_ago)).isoformat()
    metadata = {"avatarName": "abi_running", "abi_run": marker}
    return {
        "id": "run-1",
        "name": "Diseñando el plan · 1m 18s",
        "start": (NOW - timedelta(seconds=start_ago)).isoformat(),
        "end": end,
        "metadata": json.dumps(metadata) if as_json else metadata,
    }


class TestFindActiveRun:
    def test_fresh_heartbeat_is_followed(self):
        step, mode = find_active_run([{"id": "msg", "metadata": {}}, _run_step()], NOW)
        assert step["id"] == "run-1" and mode == "follow"

    def test_metadata_stored_as_json_string(self):
        _, mode = find_active_run([_run_step(as_json=True)], NOW)
        assert mode == "follow"

    def test_stale_heartbeat_is_interrupted(self):
        _, mode = find_active_run([_run_step(beat_ago=31)], NOW)
        assert mode == "interrupted"

    def test_missing_heartbeat_is_interrupted(self):
        _, mode = find_active_run([_run_step(beat_ago=None)], NOW)
        assert mode == "interrupted"

    def test_finished_runs_are_ignored(self):
        assert find_active_run([_run_step(state="done")], NOW) == (None, None)
        assert find_active_run([_run_step(end=NOW.isoformat())], NOW) == (None, None)
        assert find_active_run([{"id": "x", "metadata": {"avatarName": "abi_idle"}}], NOW) == (None, None)

    def test_latest_running_step_wins(self):
        old = {**_run_step(beat_ago=500), "id": "run-old"}
        step, mode = find_active_run([old, _run_step()], NOW)
        assert step["id"] == "run-1" and mode == "follow"


class TestResumedPage:
    def test_counter_computed_from_start(self):
        assert running_name(_run_step(start_ago=83), NOW) == "Diseñando el plan · 1m 23s"

    def test_falls_back_to_stored_name_without_label(self):
        assert running_name(_run_step(label=None), NOW) == "Diseñando el plan · 1m 18s"

    def test_still_running(self):
        assert is_still_running(_run_step(), NOW)
        assert not is_still_running(_run_step(beat_ago=40), NOW)
        assert not is_still_running(_run_step(state="stopped"), NOW)

    def test_interrupted_name(self):
        assert interrupted_name(_run_step(start_ago=125), "es-ES", NOW) == "Interrumpido · 2m 05s"
        assert interrupted_name(_run_step(start_ago=5), "en", NOW) == "Interrupted · 5.0s"


class TestDiffItems:
    def test_new_and_changed(self):
        _, _, known = diff_items({}, [{"id": "a", "output": "1"}, {"id": "b", "output": "x"}])
        new, changed, known = diff_items(known, [
            {"id": "a", "output": "1"}, {"id": "b", "output": "y"}, {"id": "c"},
        ])
        assert [s["id"] for s in new] == ["c"]
        assert [s["id"] for s in changed] == ["b"]
        assert set(known) == {"a", "b", "c"}

    def test_items_without_id_ignored(self):
        new, changed, known = diff_items({}, [{"output": "no id"}])
        assert new == [] and changed == [] and known == {}


class TestStopMark:
    def test_matches_only_this_run(self):
        assert stop_requested({STOP_KEY: "run-1", "abi_session_token": "t"}, "run-1")
        assert not stop_requested({STOP_KEY: "run-0"}, "run-1")
        assert not stop_requested({}, "run-1")

    def test_metadata_as_json_string(self):
        assert stop_requested(json.dumps({STOP_KEY: "run-1"}), "run-1")
        assert not stop_requested("not json", "run-1")
