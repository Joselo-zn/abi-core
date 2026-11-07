"""
Tests for the integration review (abi_core.common.integration_review):
static layer (AST) always; execution layer only with Docker + sandbox images.

Spec: .abi/specs/not-implemented/sdd-pipeline/07-deliverable-integration-review.md
"""

import textwrap

import pytest

from abi_core.common.integration_review import (
    infer_entry_point,
    review_files,
    static_findings,
)


def _d(src):
    return textwrap.dedent(src).lstrip()


PLAYER = _d("""
    class Player:
        def __init__(self, x, y):
            self.x = x
            self.speed = 5
        def shoot(self):
            pass
        def update(self):
            pass
""")


def _messages(findings, severity=None):
    return [f.message for f in findings if severity is None or f.severity == severity]


class TestStatic:
    def test_method_arity_mismatch(self):
        files = {"player.py": PLAYER, "main.py": _d("""
            from player import Player
            p = Player(1, 2)
            p.shoot([])
            p.update()
        """)}
        findings, _ = static_findings(files)
        errors = _messages(findings, "error")
        assert any("p.shoot(...)" in m and "como máximo 0" in m for m in errors)

    def test_constructor_arity_mismatch(self):
        files = {"player.py": PLAYER, "main.py": _d("""
            from player import Player
            p = Player(1)
            p.shoot(); p.update()
        """)}
        errors = _messages(static_findings(files)[0], "error")
        assert any("Player(...)" in m and "al menos 2" in m for m in errors)

    def test_import_of_missing_name(self):
        files = {"player.py": PLAYER, "main.py": "from player import Player, Bullet\n"}
        errors = _messages(static_findings(files)[0], "error")
        assert any("no define `Bullet`" in m for m in errors)

    def test_missing_method(self):
        files = {"player.py": PLAYER, "main.py": _d("""
            from player import Player
            p = Player(1, 2)
            p.jump()
            p.shoot(); p.update()
        """)}
        errors = _messages(static_findings(files)[0], "error")
        assert any("no tiene el método `jump`" in m for m in errors)

    def test_instance_attribute_callable_is_not_a_missing_method(self):
        files = {"a.py": _d("""
            class A:
                def __init__(self, cb):
                    self.cb = cb
        """), "main.py": "from a import A\nx = A(print)\nx.cb('hi')\n"}
        assert not _messages(static_findings(files)[0], "error")

    def test_self_attribute_instances_are_tracked(self):
        files = {"player.py": PLAYER, "game.py": _d("""
            from player import Player
            class Game:
                def __init__(self):
                    self.player = Player(0, 0)
                def tick(self):
                    self.player.shoot(1)
                    self.player.update()
        """)}
        errors = _messages(static_findings(files)[0], "error")
        assert any("self.player.shoot(...)" in m for m in errors)

    def test_unwired_public_method_is_a_warning(self):
        files = {"player.py": PLAYER, "main.py": "from player import Player\np = Player(1, 2)\np.shoot()\n"}
        findings, _ = static_findings(files)
        assert any("Player.update()" in m for m in _messages(findings, "warning"))
        assert not _messages(findings, "error")

    def test_inherited_classes_are_not_judged(self):
        files = {"s.py": _d("""
            import pygame
            class S(pygame.sprite.Sprite):
                def __init__(self):
                    super().__init__()
        """), "main.py": "from s import S\nx = S()\nx.kill()\n"}
        assert not _messages(static_findings(files)[0], "error")

    def test_syntax_error(self):
        files = {"a.py": "def broken(:\n", "main.py": "import a\n"}
        assert any("sintaxis" in m for m in _messages(static_findings(files)[0], "error"))

    def test_unknown_module_is_a_warning(self):
        files = {"a.py": "import flask\n", "main.py": "import a\n"}
        warnings = _messages(static_findings(files)[0], "warning")
        assert any("flask" in m for m in warnings)

    def test_readme_mentions_missing_file(self):
        files = {"player.py": PLAYER, "main.py": "from player import Player\nPlayer(1,2).shoot()\n",
                 "README.md": "Run `python pacman.py`"}
        assert any("pacman.py" in m for m in _messages(static_findings(files)[0], "warning"))


class TestEntryPoint:
    def test_the_file_nobody_imports(self):
        import ast
        files = {"player.py": PLAYER, "enemies.py": "class E: pass\n",
                 "game.py": "from player import Player\nfrom enemies import E\n"}
        trees = {k: ast.parse(v) for k, v in files.items()}
        assert infer_entry_point(trees) == "game.py"


class TestReview:
    @pytest.mark.asyncio
    async def test_single_file_is_not_reviewed(self):
        assert await review_files({"main.py": "print(1)"}) is None

    @pytest.mark.asyncio
    async def test_static_only(self):
        files = {"player.py": PLAYER, "main.py": "from player import Player\nPlayer(1,2).shoot(3)\n"}
        report = await review_files(files, run_sandbox=False)
        assert not report.passed and report.layer2_skipped == "desactivada"
        assert "❌" in report.as_text()


class TestUnverified:
    """A set that should have run in the sandbox and didn't is NOT a pass
    (live 2026-10-05: sandbox timeout after a repair → reported clean)."""

    FILES = {"fleet.py": "class Fleet:\n    def size(self):\n        return 3\n",
             "main.py": "from fleet import Fleet\nprint(Fleet().size())\n"}

    @pytest.mark.asyncio
    async def test_sandbox_failure_is_unverified_after_one_retry(self, monkeypatch):
        import abi_core.common.sandbox as sb
        calls = []

        async def broken(*a, **k):
            calls.append(1)
            return sb.SandboxResult(exit_code=None, timed_out=True,
                                    error="sandbox did not return within its time budget")
        monkeypatch.setattr(sb, "run_in_sandbox", broken)
        report = await review_files(self.FILES)
        assert len(calls) == 2                        # one retry
        assert report.passed and report.execution_unverified
        assert "Sin verificar" in report.as_text() and "Sin hallazgos" not in report.as_text()

    @pytest.mark.asyncio
    async def test_retry_that_succeeds_is_verified(self, monkeypatch):
        import abi_core.common.sandbox as sb
        results = [sb.SandboxResult(exit_code=None, error="transient"), sb.SandboxResult(exit_code=0)]

        async def flaky(*a, **k):
            return results.pop(0)
        monkeypatch.setattr(sb, "run_in_sandbox", flaky)
        report = await review_files(self.FILES)
        assert report.layer2_ran and not report.execution_unverified

    @pytest.mark.asyncio
    async def test_explicit_opt_out_is_not_unverified(self):
        report = await review_files(self.FILES, run_sandbox=False)
        assert not report.execution_unverified


def _sandbox_ready():
    try:
        from abi_core.common.container_runtime import _get_docker_client
        from abi_core.common.sandbox import SANDBOX_IMAGE_PYTHON
        _get_docker_client().images.get(SANDBOX_IMAGE_PYTHON)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _sandbox_ready(), reason="Docker or sandbox image not available")
class TestExecutionLayer:
    @pytest.mark.asyncio
    async def test_runtime_error_is_reported(self):
        files = {"fleet.py": "class Fleet:\n    def __init__(self):\n        self.ships = []\n",
                 "main.py": "from fleet import Fleet\nf = Fleet()\nprint(len(f))\n"}
        report = await review_files(files)
        assert report.layer2_ran and not report.passed
        assert any("has no len()" in f.message for f in report.errors)

    @pytest.mark.asyncio
    async def test_working_set_passes(self):
        files = {"fleet.py": "class Fleet:\n    def size(self):\n        return 3\n",
                 "main.py": "from fleet import Fleet\nprint(Fleet().size())\n"}
        report = await review_files(files)
        assert report.layer2_ran and report.passed

    @pytest.mark.asyncio
    async def test_interactive_input_is_a_warning(self):
        files = {"util.py": "def greet(n):\n    return 'hi ' + n\n",
                 "main.py": "from util import greet\nprint(greet(input()))\n"}
        report = await review_files(files)
        assert report.passed and any("entrada interactiva" in f.message for f in report.warnings)


class TestTracebackDetail:
    """The message names the failure; the frames go apart, for the delivery
    card to show on demand. No sandbox: its result is stubbed."""

    STDERR = ('Traceback (most recent call last):\n'
              '  File "/app/main.py", line 3, in <module>\n'
              '    print(len(f))\n'
              "TypeError: object of type 'Fleet' has no len()\n")

    async def _finding(self, monkeypatch, stderr, exit_code=1, stdout=""):
        from types import SimpleNamespace
        from abi_core.common import integration_review as ir, sandbox
        result = SimpleNamespace(error=None, oom_killed=False, timed_out=False, exit_code=exit_code,
                                 stderr=stderr, stdout=stdout)

        async def run_in_sandbox(*a, **k):
            return result

        monkeypatch.setattr(sandbox, "run_in_sandbox", run_in_sandbox)
        findings, ran, _ = await ir.execution_findings({"main.py": "print(1)\n"}, "main.py")
        assert ran and len(findings) == 1
        return findings[0]

    @pytest.mark.asyncio
    async def test_error_keeps_the_failure_in_the_message_and_the_frames_apart(self, monkeypatch):
        f = await self._finding(monkeypatch, self.STDERR)
        assert f.severity == "error"
        assert f.message == "falla al ejecutarse: TypeError: object of type 'Fleet' has no len()"
        assert f.detail == ('Traceback (most recent call last):\nFile "/app/main.py", line 3, in <module>\n'
                            "print(len(f))")

    @pytest.mark.asyncio
    async def test_the_text_for_the_reviewer_still_has_the_frames(self, monkeypatch):
        text = (await self._finding(monkeypatch, self.STDERR)).as_text()
        assert text.startswith("[main.py] falla al ejecutarse: TypeError")
        assert 'File "/app/main.py", line 3' in text and "\n" not in text

    @pytest.mark.asyncio
    async def test_interactive_input_stays_a_warning(self, monkeypatch):
        stderr = "Traceback (most recent call last):\n  File \"main.py\", line 1\nEOFError: EOF when reading a line\n"
        f = await self._finding(monkeypatch, stderr)
        assert f.severity == "warning" and "entrada interactiva" in f.message and "line 1" in f.detail

    @pytest.mark.asyncio
    async def test_a_bad_exit_without_a_traceback(self, monkeypatch):
        f = await self._finding(monkeypatch, "", exit_code=3, stdout="salida")
        assert f.message == "terminó con código 3: salida" and f.detail is None

    def test_a_finding_without_detail_reads_as_before(self):
        from abi_core.common.integration_review import Finding
        assert Finding("error", 1, "a.py", 2, "mal").as_text() == "[a.py:2] mal"


class TestReportLanguage:
    def _report(self, **changes):
        from abi_core.common.integration_review import Finding, IntegrationReport
        findings = [Finding("error", 2, "main.py", None, "falla al ejecutarse: X", "frame", en="fails when run: X"),
                    Finding("warning", 1, "a.py", 2, "sin uso", en="unused")]
        return IntegrationReport("main.py", findings, layer2_ran=True, **changes)

    def test_failed_report_in_english_has_no_spanish(self):
        text = self._report().as_text("en")
        assert "Integration review" in text and "Entry point: `main.py`" in text and "1 error(s)" in text
        assert "fails when run: X" in text and "[a.py:2] unused" in text
        for spanish in ("Revisión", "Punto de entrada", "advertencia", "falla al", "sin uso"):
            assert spanish not in text

    def test_spanish_stays_the_default(self):
        report = self._report()
        assert report.as_text() == report.as_text("es") and "Revisión de integración" in report.as_text()
        assert "falla al ejecutarse: X" in report.as_text()

    def test_pass_text_in_both_languages(self):
        from abi_core.common.integration_review import IntegrationReport
        ran = IntegrationReport("main.py", layer2_ran=True)
        assert ran.as_pass_text("en").startswith("✅ Verified by code") and "`main.py` ran" in ran.as_pass_text("en")
        assert ran.as_pass_text().startswith("✅ Verificado por código")
        off = IntegrationReport("main.py", layer2_skipped="desactivada")
        assert "They were not run (turned off)" in off.as_pass_text("en")
        assert "No se ejecutaron (desactivada)" in off.as_pass_text()

    def test_a_skip_reason_with_the_sandbox_error(self):
        from abi_core.common.integration_review import IntegrationReport
        report = IntegrationReport("main.py", layer2_skipped="no se pudo ejecutar: sandbox denied")
        assert "could not run: sandbox denied" in report.as_text("en")

    def test_static_findings_carry_both_languages(self):
        from abi_core.common.integration_review import static_findings
        findings, _ = static_findings({"a.py": "def f(x):\n    return x\n",
                                       "main.py": "from a import f, g\nf()\nf(1, 2)\nf(1, y=2)\n"})
        errors = [f for f in findings if f.severity == "error"]
        assert len(errors) == 4 and all(f.en and f.en != f.message for f in errors)
        assert not any(w in f.en for f in errors for w in ("recibe", "no define", "desconocido"))

    def test_the_links_heading(self):
        from abi_core.common.artifact_store import format_artifact_links
        arts = [{"filename": "a.txt", "download_url": "/x"}]
        assert "**Generated files:**" in format_artifact_links(arts)
        assert "**Archivos generados:**" in format_artifact_links(arts, "es")

