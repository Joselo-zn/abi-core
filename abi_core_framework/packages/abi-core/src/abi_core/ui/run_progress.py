"""Human-readable progress of one agent run, built from status ``phase`` meta.

Pure state + text formatting, no Chainlit import — chainlit_app.py owns the
``cl.Step`` objects and just renders what this produces. See
.abi/specs/not-implemented/ux/chainlit-run-progress-indicator.md.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

# (running label, completed label) per phase. "awaiting_confirmation" is never
# emitted by an agent — it only appears as a pending step after planning.
_PHASE_LABELS = {
    "es": {
        "analyzing": ("Entendiendo tu solicitud", "Solicitud entendida"),
        "routing": ("Decidiendo cómo resolverlo", "Estrategia elegida"),
        "planning": ("Diseñando el plan", "Plan diseñado"),
        "awaiting_confirmation": ("Esperando tu aprobación", "Plan aprobado"),
        "building": ("Preparando agentes", "Agentes listos"),
        "executing": ("Ejecutando", "Ejecución completa"),
        "synthesizing": ("Redactando la respuesta", "Respuesta lista"),
    },
    "en": {
        "analyzing": ("Understanding your request", "Request understood"),
        "routing": ("Deciding how to solve it", "Strategy chosen"),
        "planning": ("Designing the plan", "Plan designed"),
        "awaiting_confirmation": ("Waiting for your approval", "Plan approved"),
        "building": ("Preparing agents", "Agents ready"),
        "executing": ("Running", "Run complete"),
        "synthesizing": ("Writing the answer", "Answer ready"),
    },
}

_TEXT = {
    "es": {
        "working": "Trabajando",
        "executing_step": "Ejecutando · paso {i} de {n}",
        "executing_steps": "Ejecutando · pasos {list} de {n}",
        "and": "y",
        "step": "Paso {i}/{n} · {label}",
        "done": "Listo",
        "plan_ready": "Esperando tu confirmación",
        "needs_input": "Necesito tu respuesta",
        "failed": "Falló en: {label}",
        "stopped": "Detenido",
        "working_on": "Trabajando en {file}…",
        "working_plain": "Trabajando…",
        "file_done": "✓ Archivo generado: {files}",
        "files_done": "✓ Archivos generados: {files}",
        "task_done": "✓ Listo",
        "task_failed": "✕ No se completó",
        "error_timeout": "Esto está tardando más de lo esperado (más de {seconds}s): probablemente el modelo está sobrecargado. Intentá de nuevo.",
        "error_timeout_plain": "Esto está tardando más de lo esperado: probablemente el modelo está sobrecargado. Intentá de nuevo.",
    },
    "en": {
        "working": "Working",
        "executing_step": "Running · step {i} of {n}",
        "executing_steps": "Running · steps {list} of {n}",
        "and": "and",
        "step": "Step {i}/{n} · {label}",
        "done": "Done",
        "plan_ready": "Waiting for your confirmation",
        "needs_input": "Your input is needed",
        "failed": "Failed at: {label}",
        "stopped": "Stopped",
        "working_on": "Working on {file}…",
        "working_plain": "Working…",
        "file_done": "✓ File created: {files}",
        "files_done": "✓ Files created: {files}",
        "task_done": "✓ Done",
        "task_failed": "✕ Not completed",
        "error_timeout": "This is taking longer than expected (over {seconds}s); the model is probably overloaded. Try again.",
        "error_timeout_plain": "This is taking longer than expected; the model is probably overloaded. Try again.",
    },
}

# Pending steps are shown only where the path ahead is actually known — a
# routed request may just as well be answered directly, so nothing is
# promised after analyzing/routing.
_NEXT_PHASES = {
    "planning": ["awaiting_confirmation"],
    "building": ["executing", "synthesizing"],
    "executing": ["synthesizing"],
}

_DETAIL_MAX = 120

# A status that is just a short generic phrase ("Executing pipeline...",
# "Still working...") — an agent's heartbeat, not information for the user.
_GENERIC_STATUS = re.compile(r"^[A-Z][\w ]{2,40}\.\.\.$")
_RESULT_MAX = 280


def _one_line(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_task_update(text: str, lang: str, deliverable: Optional[str] = None) -> str:
    """Readable body for a plan task's step from one of its raw updates.

    - An agent's result payload (JSON with ``status`` / ``uploaded_artifacts``,
      as ephemeral agents and the Planner's direct tools return it) becomes
      "✓ File created: player.py" plus the agent's own message — never the
      artifact store's internal URLs.
    - A failed or incomplete payload becomes "✕ Not completed" plus why.
    - A generic heartbeat ("Executing pipeline...") becomes
      "Working on player.py…" (or "Working…" without a known deliverable).
    - Anything else is shown as is.
    """
    t = _TEXT[ui_language(lang)]
    raw = (text or "").strip()

    payload = None
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            payload = None
    if isinstance(payload, dict) and ("status" in payload or "uploaded_artifacts" in payload):
        status = str(payload.get("status", "completed")).lower()
        message = payload.get("error") or payload.get("result") or ""
        if status not in ("completed", "success", "ok"):
            lines = [t["task_failed"]]
        else:
            files = [a.get("filename") for a in payload.get("uploaded_artifacts") or []
                     if isinstance(a, dict) and a.get("filename")]
            if len(files) == 1:
                lines = [t["file_done"].format(files=files[0])]
            elif files:
                lines = [t["files_done"].format(files=", ".join(files))]
            else:
                lines = [t["task_done"]]
        if message:
            lines.append(_one_line(message, _RESULT_MAX))
        return "\n".join(lines)

    if not raw or _GENERIC_STATUS.match(raw):
        return t["working_on"].format(file=deliverable) if deliverable else t["working_plain"]
    return raw


def ui_language(language: Optional[str]) -> str:
    """Map a browser/Chainlit language tag ("es-ES", "en-US", ...) to a
    supported label set."""
    return "es" if (language or "").lower().startswith("es") else "en"


def error_message(lang: str, meta: Optional[dict]) -> Optional[str]:
    """User-facing text for an error the agent tagged with ``meta.error_code``,
    in the UI language; None for codes without a translation (the caller
    keeps its generic message)."""
    meta = meta or {}
    if meta.get("error_code") == "timeout":
        text = _TEXT[ui_language(lang)]
        if meta.get("max_wait"):
            return "⏱️ " + text["error_timeout"].format(seconds=meta["max_wait"])
        return "⏱️ " + text["error_timeout_plain"]
    return None


def format_duration(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs:02d}s"


def task_step_name(lang: str, label: Optional[str], task_key: Optional[str],
                   index: Optional[int], total: Optional[int]) -> str:
    """Name for a per-task child step: "Paso 2/3 · <description>".

    Strips the "task_N: " prefix workflow node labels carry, since the
    position already says which task it is.
    """
    label = label or task_key or ""
    if task_key and label.startswith(f"{task_key}: "):
        label = label[len(task_key) + 2:]
    if index and total:
        return _TEXT[lang]["step"].format(i=index, n=total, label=label)
    return label


@dataclass
class _PhaseEntry:
    phase: str
    start: float
    end: Optional[float] = None
    detail: Optional[str] = None
    task_index: Optional[int] = None
    task_total: Optional[int] = None
    # Plan tasks running at the same time (independent tasks run in
    # parallel), as 1-based step numbers.
    running: Optional[list] = None


class RunProgress:
    """Timeline of the phases one run went through."""

    def __init__(self, language: Optional[str], clock: Callable[[], float] = time.monotonic):
        self.lang = ui_language(language)
        self._clock = clock
        self._t0 = clock()
        self.phases: list[_PhaseEntry] = []

    @property
    def current(self) -> Optional[_PhaseEntry]:
        if self.phases and self.phases[-1].end is None:
            return self.phases[-1]
        return None

    def advance(self, phase: str, detail: Optional[str] = None,
                task_index: Optional[int] = None, task_total: Optional[int] = None,
                running: Optional[list] = None) -> None:
        """Record a status update for *phase*, opening a new timeline entry
        when the phase changes. Unknown phases are ignored."""
        if phase not in _PHASE_LABELS[self.lang]:
            return
        now = self._clock()
        entry = self.current
        if entry is None or entry.phase != phase:
            if entry is not None:
                entry.end = now
            entry = _PhaseEntry(phase=phase, start=now)
            self.phases.append(entry)
        if detail:
            entry.detail = " ".join(detail.split())[:_DETAIL_MAX]
        if task_index:
            entry.task_index = task_index
        if task_total:
            entry.task_total = task_total
        if running is not None:
            entry.running = sorted(i for i in running if i)

    def finish(self) -> None:
        if self.current is not None:
            self.current.end = self._clock()

    def elapsed(self) -> float:
        return self._clock() - self._t0

    def _running_label(self, entry: _PhaseEntry) -> str:
        text = _TEXT[self.lang]
        if entry.phase == "executing" and entry.task_total and entry.running and len(entry.running) > 1:
            *rest, last = [str(i) for i in entry.running]
            listed = f"{', '.join(rest)} {text['and']} {last}"
            return text["executing_steps"].format(list=listed, n=entry.task_total)
        if entry.phase == "executing" and entry.task_total and entry.running:
            return text["executing_step"].format(i=entry.running[0], n=entry.task_total)
        if entry.phase == "executing" and entry.task_index and entry.task_total:
            return text["executing_step"].format(i=entry.task_index, n=entry.task_total)
        return _PHASE_LABELS[self.lang][entry.phase][0]

    def label(self) -> str:
        """What is running right now, without the elapsed time — stored in
        the run step's metadata so a resumed page can add the time itself."""
        entry = self.current
        return self._running_label(entry) if entry else _TEXT[self.lang]["working"]

    def header(self) -> str:
        """Step name while running: current phase + total elapsed."""
        return f"{self.label()} · {format_duration(self.elapsed())}"

    def summary(self, outcome: str) -> str:
        """Step name once the run stopped (call finish() first)."""
        text = _TEXT[self.lang]
        if outcome == "failed":
            last = self.phases[-1] if self.phases else None
            where = self._running_label(last) if last else text["working"]
            label = text["failed"].format(label=where)
        else:
            label = text.get(outcome, text["done"])
        return f"{label} · {format_duration(self.elapsed())}"

    def timeline(self, failed: bool = False) -> str:
        """Markdown checklist: ✓ completed, ● running, ✕ failed, ○ pending."""
        lines = []
        now = self._clock()
        for i, entry in enumerate(self.phases):
            is_last = i == len(self.phases) - 1
            running_label, done_label = _PHASE_LABELS[self.lang][entry.phase]
            duration = format_duration((entry.end or now) - entry.start)
            if entry.end is None:
                lines.append(f"● **{self._running_label(entry)}…** · {duration}")
            elif failed and is_last:
                lines.append(f"✕ {running_label} · {duration}")
            else:
                lines.append(f"✓ {done_label} · {duration}")
            if entry.detail and (entry.end is None or (failed and is_last)):
                lines.append(f"    ↳ {entry.detail}")

        current = self.current
        if current is not None:
            for phase in _NEXT_PHASES.get(current.phase, []):
                lines.append(f"○ {_PHASE_LABELS[self.lang][phase][0]}")
        # Chainlit renders step output with white-space: pre-wrap, so a plain
        # newline already breaks the line (a markdown hard break doubles it).
        return "\n".join(lines)
