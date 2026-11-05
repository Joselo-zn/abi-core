"""Limit notices sent as a key: the Chat UI writes them in the UI language.
Keys and params: .abi/specs/not-implemented/gcp-workflows/gcp-workflows-pipelines.md,
"Avisos de límite".
"""

from datetime import datetime, timezone

from abi_core.ui.run_progress import notice_message

NOW = datetime(2026, 11, 1, 18, 40, tzinfo=timezone.utc)
META = {"notice": {"key": "limit.plans_per_day", "params": {"limit": 5, "resets_at": "2026-11-02T00:00:00Z"}}}


def test_a_known_key_is_written_in_the_ui_language():
    assert notice_message("es-ES", META, NOW) == (
        "Llegaste al límite de 5 planes de hoy. Puedes seguir conversando; podrás crear otro en 5 h 20 min.")
    assert notice_message("en-US", META, NOW).startswith("You reached today's limit of 5 plans.")


def test_minutes_only_when_under_an_hour_and_no_reset_for_active_workflows():
    soon = {"notice": {"key": "limit.messages_per_day", "params": {"limit": 50, "resets_at": "2026-11-01T19:05:00Z"}}}
    assert notice_message("es", soon, NOW).endswith("Se renueva en 25 min.")
    active = {"notice": {"key": "limit.active_workflows", "params": {"limit": 3}}}
    assert notice_message("es", active, NOW) == "Ya tienes 3 workflows activos, el máximo. Borra uno para crear otro."


def test_unknown_key_missing_params_or_no_notice_fall_back_to_the_agents_text():
    assert notice_message("es", {"notice": {"key": "limit.unknown", "params": {}}}, NOW) is None
    assert notice_message("es", {"notice": {"key": "limit.plans_per_day", "params": {}}}, NOW) is None
    assert notice_message("es", None, NOW) is None
    assert notice_message("es", {"error_code": "timeout"}, NOW) is None
