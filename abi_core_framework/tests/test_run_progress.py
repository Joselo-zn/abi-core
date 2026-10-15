"""
Tests for the Chainlit run progress indicator: phase timeline
(abi_core.ui.run_progress), translation defaults (abi_core.ui.translations)
and phase propagation through AbiAgent._run_with_heartbeat.
"""

import asyncio
import json

import pytest

from abi_core.agent.agent_response import AgentResponse, RunPhase
from abi_core.ui.run_progress import RunProgress, format_duration, task_step_name, ui_language


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


class TestFormatting:
    def test_durations(self):
        assert format_duration(1.23) == "1.2s"
        assert format_duration(23.9) == "23s"
        assert format_duration(72) == "1m 12s"

    def test_language(self):
        assert ui_language("es-ES") == "es"
        assert ui_language("es") == "es"
        assert ui_language("en-US") == "en"
        assert ui_language(None) == "en"

    def test_task_step_name_strips_node_prefix(self):
        name = task_step_name("es", "task_2: Implementar movimiento", "task_2", 2, 3)
        assert name == "Paso 2/3 · Implementar movimiento"

    def test_task_step_name_without_position(self):
        assert task_step_name("en", "task_1: Build it", "task_1", None, None) == "Build it"


class TestRunProgress:
    def test_header_before_any_phase(self, clock):
        progress = RunProgress("es", clock=clock)
        assert progress.header() == "Trabajando · 0.0s"

    def test_phase_change_closes_previous(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.ANALYZING.value)
        clock.now = 1.2
        progress.advance(RunPhase.PLANNING.value)
        clock.now = 23.5
        progress.advance(RunPhase.PLANNING.value)  # heartbeat, same phase

        assert [p.phase for p in progress.phases] == ["analyzing", "planning"]
        assert progress.header() == "Diseñando el plan · 23s"
        timeline = progress.timeline().split("\n")
        assert timeline[0] == "✓ Solicitud entendida · 1.2s"
        assert timeline[1] == "● **Diseñando el plan…** · 22s"
        assert timeline[2] == "○ Esperando tu aprobación"

    def test_no_pending_promised_after_routing(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.ROUTING.value)
        assert "○" not in progress.timeline()

    def test_executing_header_uses_task_position(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.EXECUTING.value, detail="Builder creando el agente",
                         task_index=2, task_total=3)
        assert progress.header().startswith("Ejecutando · paso 2 de 3")
        assert "↳ Builder creando el agente" in progress.timeline()

    def test_unknown_phase_is_ignored(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance("teleporting")
        assert progress.phases == []

    def test_summary_plan_ready(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.PLANNING.value)
        clock.now = 34
        progress.finish()
        assert progress.summary("plan_ready") == "Esperando tu confirmación · 34s"
        assert progress.timeline() == "✓ Plan diseñado · 34s"

    def test_summary_failed_marks_last_phase(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.PLANNING.value, detail="timeout del modelo")
        clock.now = 123
        progress.finish()
        assert progress.summary("failed") == "Falló en: Diseñando el plan · 2m 03s"
        timeline = progress.timeline(failed=True)
        assert timeline.startswith("✕ Diseñando el plan · 2m 03s")
        assert "↳ timeout del modelo" in timeline

    def test_detail_is_single_line_and_truncated(self, clock):
        progress = RunProgress("en", clock=clock)
        progress.advance(RunPhase.EXECUTING.value, detail="line one\nline two " + "x" * 300)
        detail = progress.current.detail
        assert "\n" not in detail
        assert len(detail) == 120


class TestTranslations:
    def test_blanks_prefix_and_keeps_existing_files(self, tmp_path):
        pytest.importorskip("chainlit")
        from abi_core.ui.translations import write_default_translations

        own = tmp_path / "es.json"
        own.write_text('{"custom": true}', encoding="utf-8")

        written = write_default_translations(tmp_path)

        assert own not in written
        assert json.loads(own.read_text(encoding="utf-8")) == {"custom": True}
        en = json.loads((tmp_path / "en-US.json").read_text(encoding="utf-8"))
        assert en["chat"]["messages"]["status"] == {"using": "", "used": ""}


class TestHeartbeatPhase:
    def _heartbeats(self, phase):
        from abi_core.agent.agent import AbiAgent, _HeartbeatDone

        agent = AbiAgent.__new__(AbiAgent)
        agent.agent_name = "tester"

        async def slow():
            await asyncio.sleep(0.05)
            return "done"

        async def collect():
            items = []
            async for item in agent._run_with_heartbeat(
                slow(), "ctx", "task", "Working...", interval=0.01, phase=phase,
            ):
                if not isinstance(item, _HeartbeatDone):
                    items.append(item)
            return items

        return asyncio.run(collect())

    def test_phase_carried_in_meta(self):
        beats = self._heartbeats(RunPhase.PLANNING.value)
        assert beats
        assert all(b["meta"]["phase"] == "planning" for b in beats)

    def test_no_phase_key_when_omitted(self):
        beats = self._heartbeats(None)
        assert beats
        assert all("phase" not in b["meta"] for b in beats)


def test_status_meta_passthrough():
    status = AgentResponse.status("x", phase=RunPhase.EXECUTING.value, task_index=1)
    assert status["meta"] == {"phase": "executing", "task_index": 1}


class TestParallelSteps:
    def test_several_running_steps_listed(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.EXECUTING.value, task_index=3, task_total=5, running=[4, 2, 3])
        assert progress.header().startswith("Ejecutando · pasos 2, 3 y 4 de 5")

    def test_one_running_step_wins_over_last_sender(self, clock):
        progress = RunProgress("en", clock=clock)
        progress.advance(RunPhase.EXECUTING.value, task_index=3, task_total=5, running=[2, 3])
        progress.advance(RunPhase.EXECUTING.value, task_index=3, task_total=5, running=[3])
        assert progress.header().startswith("Running · step 3 of 5")

    def test_without_running_info_uses_task_index(self, clock):
        progress = RunProgress("es", clock=clock)
        progress.advance(RunPhase.EXECUTING.value, task_index=2, task_total=5)
        assert progress.header().startswith("Ejecutando · paso 2 de 5")


class TestFormatTaskUpdate:
    from abi_core.ui.run_progress import format_task_update as _fmt
    fmt = staticmethod(_fmt)

    PLAYER = json.dumps({
        "status": "completed", "result": "",
        "uploaded_artifacts": [{"filename": "player.py", "key": "ephemeral-task-3-1791085176/player.py",
                                "url": "http://abi-swarm-minio:9000/abi-artifacts/ephemeral-task-3-1791085176/player.py",
                                "agent": "ephemeral-task-3-1791085176"}],
        "agent": "ephemeral-task-3-1791085176",
    })

    def test_completed_shows_file_not_internal_url(self):
        out = self.fmt(self.PLAYER, "es")
        assert out == "✓ Archivo generado: player.py"
        assert "minio" not in out and "ephemeral" not in out

    def test_completed_keeps_agent_message_on_one_line(self):
        payload = json.dumps({"status": "completed", "result": "The `enemies.py` file\nhas been created.",
                              "uploaded_artifacts": [{"filename": "enemies.py"}]})
        assert self.fmt(payload, "en") == "✓ File created: enemies.py\nThe `enemies.py` file has been created."

    def test_several_files(self):
        payload = json.dumps({"status": "completed", "uploaded_artifacts": [{"filename": "a.py"}, {"filename": "b.py"}]})
        assert self.fmt(payload, "es") == "✓ Archivos generados: a.py, b.py"

    def test_incomplete_or_error(self):
        assert self.fmt(json.dumps({"status": "incompleted", "result": "upload failed"}), "es") == "✕ No se completó\nupload failed"
        assert self.fmt(json.dumps({"status": "error", "error": "timeout"}), "en") == "✕ Not completed\ntimeout"

    def test_generic_heartbeat(self):
        assert self.fmt("Executing pipeline...", "es", "game_logic.py") == "Trabajando en game_logic.py…"
        assert self.fmt("Still working...", "en") == "Working…"

    def test_other_text_unchanged(self):
        assert self.fmt("task_1 no produjo el archivo esperado, reintentando con un nuevo agente...", "es").startswith("task_1 no produjo")
        assert self.fmt('{"a": 1}', "es") == '{"a": 1}'
