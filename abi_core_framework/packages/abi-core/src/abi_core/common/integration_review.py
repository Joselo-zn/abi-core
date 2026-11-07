"""
Integration review — does a set of generated files work *together*?

Phase 2.5 checks that every file exists; this checks the set. Two layers:

    Layer 1 — static (AST, no execution, no LLM): syntax, imports between
              files, call arity against the callee's real signature,
              public methods nobody calls, README pointing at missing files.
    Layer 2 — execution in the sandbox (abi_core.common.sandbox): the entry
              point runs headless; a traceback is an error.

The command for layer 2 is chosen here, by code (domain adapters), never by
an LLM. Spec: .abi/specs/not-implemented/sdd-pipeline/07-deliverable-integration-review.md

Usage:
    report = await review_files({"game.py": src, "player.py": src2, ...})
    if report.errors: ...
    print(report.as_text())
"""

import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Third-party modules the sandbox images provide (sandbox-images/).
SANDBOX_THIRD_PARTY = {"pygame", "numpy"}

LAYER2_TIMEOUT_S = int(os.getenv("INTEGRATION_REVIEW_RUN_SECONDS", "15"))
WEB_CHECK_TIMEOUT_S = int(os.getenv("WEB_CHECK_RUN_SECONDS", "60"))
WEB_CHECK_MEMORY_MB = int(os.getenv("WEB_CHECK_MEMORY_MB", "1024"))
WEB_CHECK_PIDS = int(os.getenv("WEB_CHECK_PIDS", "256"))

# task_id prefix of the former integration reviewer ephemeral. The repair is
# now one model call in the Orchestrator (integration_repair.py); the zombie
# still honours the prefix (partial rewrites kept if it stops early) for
# any older Orchestrator that spawns a reviewer ephemeral.
REVIEW_TASK_PREFIX = "integration_review_"


@dataclass
class Finding:
    severity: str            # "error" | "warning" | "info"
    layer: int               # 1 static, 2 execution
    file: str
    line: Optional[int]
    message: str
    detail: Optional[str] = None  # the traceback's frames: shown on demand, one per line
    en: Optional[str] = None      # the message in English

    def text(self, lang: str = "es") -> str:
        return self.en if lang == "en" and self.en else self.message

    def as_text(self, lang: str = "es") -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        text = f"[{where}] {self.text(lang)}"
        # Whoever reads this text (the reviewer, the chat) needs the frames too.
        return f"{text} ⏎ {self.detail.replace(chr(10), ' ⏎ ')}" if self.detail else text


_COULD_NOT_RUN = "no se pudo ejecutar"
_EXTERNAL = "depende de recursos externos"
_SKIPPED_EN = {"desactivada": "turned off",
               "no se identificó el punto de entrada": "the entry point could not be identified",
               "hay errores de sintaxis": "there are syntax errors"}
_REPORT_TEXT = {
    "es": {
        "title": "**Revisión de integración de los archivos entregados**",
        "entry": "Punto de entrada: `{}`",
        "ran": "Ejecución en sandbox: sí",
        "not_ran": "Ejecución en sandbox: no ({})",
        "errors": "\n❌ {} error(es) — el conjunto no funciona tal como se entregó:",
        "unverified": ("\n⚠️ Sin verificar: la revisión estática no encontró errores, pero el conjunto "
                       "no se pudo ejecutar, así que no está comprobado que funcione."),
        "warnings": "\n⚠️ {} advertencia(s):",
        "warnings_ran": "⚠️ {} advertencia(s), que no impiden que se ejecute:",
        "clean": "\n✅ Sin hallazgos.",
        "the_entry": "el punto de entrada",
        "no_run": "sin ejecución",
        "passed": ("✅ Verificado por código: los archivos encajan entre sí y {entry} se ejecutó "
                   "en el sandbox hasta {seconds} s sin errores. Eso no prueba el uso real "
                   "(por ejemplo, que un juego se pueda jugar bien)."),
        "passed_static": "✅ Revisión estática sin errores: los archivos encajan entre sí. No se ejecutaron ({}).",
        "passed_web": ("✅ Verificado por código: {entry} se abrió en un navegador en el sandbox, con clic, "
                       "Espacio y flechas simulados, sin errores de JavaScript ni archivos faltantes. "
                       "Eso no prueba el uso real (por ejemplo, que un juego se pueda jugar bien)."),
        "unverified_web": "\n⚠️ Sin verificar: no se pudo comprobar en el navegador que funcione.",
    },
    "en": {
        "title": "**Integration review of the delivered files**",
        "entry": "Entry point: `{}`",
        "ran": "Run in the sandbox: yes",
        "not_ran": "Run in the sandbox: no ({})",
        "errors": "\n❌ {} error(s): the files do not work as delivered:",
        "unverified": ("\n⚠️ Unverified: the static review found no errors, but the files "
                       "could not be run, so it is not proven that they work."),
        "warnings": "\n⚠️ {} warning(s):",
        "warnings_ran": "⚠️ {} warning(s), which don't stop it from running:",
        "clean": "\n✅ No findings.",
        "the_entry": "the entry point",
        "no_run": "not run",
        "passed": ("✅ Verified by code: the files fit together and {entry} ran "
                   "in the sandbox for up to {seconds} s without errors. That does not prove real use "
                   "(for example, that a game plays well)."),
        "passed_static": "✅ Static review without errors: the files fit together. They were not run ({}).",
        "passed_web": ("✅ Verified by code: {entry} opened in a browser in the sandbox, with a simulated click, "
                       "Space and arrows, without JavaScript errors or missing files. "
                       "That does not prove real use (for example, that a game plays well)."),
        "unverified_web": "\n⚠️ Unverified: it could not be proven in the browser that it works.",
    },
}


@dataclass
class IntegrationReport:
    entry_point: Optional[str]
    findings: List[Finding] = field(default_factory=list)
    layer2_ran: bool = False
    layer2_skipped: Optional[str] = None
    web: bool = False                # a page checked in a browser, not a Python set

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    @property
    def execution_unverified(self) -> bool:
        """The set was supposed to run in the sandbox and didn't.

        Not a pass. Live 2026-10-05: the sandbox didn't return within its
        budget after a repair, layer 2 was skipped, layer 1 was clean — and
        the set "passed" without ever running. Only an explicit opt-out
        (INTEGRATION_REVIEW_SANDBOX=false) counts as not needing execution.
        """
        return not self.layer2_ran and self.layer2_skipped != "desactivada"

    def skipped_reason(self, lang: str = "es") -> Optional[str]:
        """Why it did not run, in the user's language."""
        if lang != "en" or not self.layer2_skipped:
            return self.layer2_skipped
        if self.layer2_skipped.startswith(_COULD_NOT_RUN):
            return "could not run" + self.layer2_skipped[len(_COULD_NOT_RUN):]
        if self.layer2_skipped.startswith(_EXTERNAL):
            return "depends on external resources" + self.layer2_skipped[len(_EXTERNAL):]
        return _SKIPPED_EN.get(self.layer2_skipped, self.layer2_skipped)

    def as_text(self, lang: str = "es") -> str:
        """Deterministic, user-facing report, in the user's language."""
        t = _REPORT_TEXT["en" if lang == "en" else "es"]
        lines = [t["title"]]
        if self.entry_point:
            lines.append(t["entry"].format(self.entry_point))
        if self.layer2_ran:
            lines.append(t["ran"])
        elif self.layer2_skipped:
            lines.append(t["not_ran"].format(self.skipped_reason(lang)))
        if self.errors:
            lines.append(t["errors"].format(len(self.errors)))
            lines += [f"- {f.as_text(lang)}" for f in self.errors]
        elif self.execution_unverified:
            lines.append(t["unverified_web"] if self.web else t["unverified"])
        if self.warnings:
            lines.append(t["warnings"].format(len(self.warnings)))
            lines += [f"- {f.as_text(lang)}" for f in self.warnings]
        if not self.errors and not self.warnings and not self.execution_unverified:
            lines.append(t["clean"])
        return "\n".join(lines)

    def as_pass_text(self, lang: str = "es") -> str:
        """Deterministic verdict for a set that passed (no errors, not
        unverified), saying exactly what the check covered — so the user's
        answer never depends on a model interpreting the review. Live
        2026-10-15: the synthesis model reported a set with 0 errors as "does
        not run" (from unused-method warnings) and another as "fully
        functional". In the user's language, like as_text()."""
        t = _REPORT_TEXT["en" if lang == "en" else "es"]
        entry = f"`{self.entry_point}`" if self.entry_point else t["the_entry"]
        if self.layer2_ran:
            lines = [t["passed_web"].format(entry=entry) if self.web
                     else t["passed"].format(entry=entry, seconds=LAYER2_TIMEOUT_S)]
            warnings_header = t["warnings_ran"].format(len(self.warnings))
        else:
            lines = [t["passed_static"].format(self.skipped_reason(lang) or t["no_run"])]
            warnings_header = t["warnings"].format(len(self.warnings)).lstrip("\n")
        if self.warnings:
            lines.append("\n" + warnings_header)
            lines += [f"- {f.as_text(lang)}" for f in self.warnings]
        return "\n".join(lines)


# ── Layer 1: static ────────────────────────────────────────────

@dataclass
class _Sig:
    min_args: int
    max_args: Optional[int]   # None = *args
    kw_names: Set[str]
    any_kwargs: bool

    def accepts(self, n_pos: int, kw: Set[str]) -> Optional[Tuple[str, str]]:
        """What is wrong with the call as (Spanish, English), or None."""
        if self.max_args is not None and n_pos > self.max_args:
            return (f"recibe {n_pos} argumento(s) posicional(es), acepta como máximo {self.max_args}",
                    f"gets {n_pos} positional argument(s), takes at most {self.max_args}")
        unknown = {k for k in kw if k not in self.kw_names} if not self.any_kwargs else set()
        if unknown:
            names = ", ".join(sorted(unknown))
            return f"argumento(s) con nombre desconocido(s): {names}", f"unknown keyword argument(s): {names}"
        provided = n_pos + len(kw & self.kw_names)
        if provided < self.min_args:
            return (f"recibe {provided} argumento(s), requiere al menos {self.min_args}",
                    f"gets {provided} argument(s), needs at least {self.min_args}")
        return None


def _signature(fn: ast.FunctionDef, drop_self: bool) -> _Sig:
    a = fn.args
    positional = list(a.posonlyargs) + list(a.args)
    if drop_self and positional:
        positional = positional[1:]
    n_defaults = len(a.defaults)
    required = len(positional) - n_defaults
    kwonly_required = sum(1 for d in a.kw_defaults if d is None)
    return _Sig(
        min_args=max(required, 0) + kwonly_required,
        max_args=None if a.vararg else len(positional),
        kw_names={p.arg for p in positional} | {p.arg for p in a.kwonlyargs},
        any_kwargs=a.kwarg is not None,
    )


@dataclass
class _ClassInfo:
    name: str
    module: str
    methods: Dict[str, _Sig]
    attrs: Set[str]            # self.x assigned anywhere in the class
    opaque: bool               # inherits from something: can't know all members
    line: int


def _is_main_guard(node: ast.AST) -> bool:
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")


def _collect(tree: ast.Module, module: str):
    classes, functions, top_names = {}, {}, set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods, attrs = {}, set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list)
                    methods[item.name] = _signature(item, drop_self=not is_static)
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                    attrs |= {t.id for t in targets if isinstance(t, ast.Name)}
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) \
                        and sub.value.id == "self" and isinstance(sub.ctx, ast.Store):
                    attrs.add(sub.attr)
            classes[node.name] = _ClassInfo(node.name, module, methods, attrs,
                                            opaque=bool(node.bases), line=node.lineno)
            top_names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = _signature(node, drop_self=False)
            top_names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        top_names.add(n.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                top_names.add((alias.asname or alias.name).split(".")[0])
    return classes, functions, top_names


def _plan_imports(tree: ast.Module, modules: Set[str]) -> Set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in modules:
                found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in modules:
                    found.add(alias.name.split(".")[0])
    return found


def infer_entry_point(trees: Dict[str, ast.Module]) -> Optional[str]:
    """The file that is run: not imported by any other file of the set,
    preferring the one that imports the most of them, then a __main__ guard."""
    modules = {f[:-3] for f in trees}
    imported_by_others: Set[str] = set()
    imports = {}
    for fname, tree in trees.items():
        imports[fname] = _plan_imports(tree, modules - {fname[:-3]})
        imported_by_others |= imports[fname]
    candidates = [f for f in trees if f[:-3] not in imported_by_others] or list(trees)
    has_guard = {f: any(_is_main_guard(n) for n in trees[f].body) for f in trees}
    candidates.sort(key=lambda f: (len(imports[f]), has_guard[f], f), reverse=True)
    return candidates[0] if candidates else None


def static_findings(files: Dict[str, str]) -> Tuple[List[Finding], Optional[str]]:
    findings: List[Finding] = []
    trees: Dict[str, ast.Module] = {}

    py_files = {k: v for k, v in files.items() if k.endswith(".py")}
    for fname, src in py_files.items():
        try:
            trees[fname] = ast.parse(src, filename=fname)
        except SyntaxError as e:
            findings.append(Finding("error", 1, fname, e.lineno, f"error de sintaxis: {e.msg}", en=f"syntax error: {e.msg}"))

    modules = {f[:-3]: f for f in trees}
    classes: Dict[str, _ClassInfo] = {}          # "module.Class" → info
    functions: Dict[str, _Sig] = {}              # "module.func" → sig
    exported: Dict[str, Set[str]] = {}
    for fname, tree in trees.items():
        mod = fname[:-3]
        c, f, names = _collect(tree, mod)
        exported[mod] = names
        classes.update({f"{mod}.{k}": v for k, v in c.items()})
        functions.update({f"{mod}.{k}": v for k, v in f.items()})

    referenced_attrs: Set[str] = set()

    for fname, tree in trees.items():
        mod = fname[:-3]
        # Names in this file bound to a plan class or function
        local_classes = {k.split(".", 1)[1]: k for k in classes if k.startswith(f"{mod}.")}
        local_funcs = {k.split(".", 1)[1]: k for k in functions if k.startswith(f"{mod}.")}

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top in modules:
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        if alias.name not in exported[top]:
                            findings.append(Finding("error", 1, fname, node.lineno,
                                f"`from {top} import {alias.name}`: `{modules[top]}` no define `{alias.name}`",
                                en=f"`from {top} import {alias.name}`: `{modules[top]}` does not define `{alias.name}`"))
                        else:
                            bound = alias.asname or alias.name
                            if f"{top}.{alias.name}" in classes:
                                local_classes[bound] = f"{top}.{alias.name}"
                            if f"{top}.{alias.name}" in functions:
                                local_funcs[bound] = f"{top}.{alias.name}"
                elif top not in sys.stdlib_module_names and top not in SANDBOX_THIRD_PARTY:
                    findings.append(Finding("warning", 1, fname, node.lineno,
                        f"importa `{node.module}`, que no está entre los archivos entregados ni en el entorno de ejecución",
                        en=f"imports `{node.module}`, which is neither among the delivered files nor in the runtime"))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in modules and top not in sys.stdlib_module_names and top not in SANDBOX_THIRD_PARTY:
                        findings.append(Finding("warning", 1, fname, node.lineno,
                            f"importa `{alias.name}`, que no está entre los archivos entregados ni en el entorno de ejecución",
                            en=f"imports `{alias.name}`, which is neither among the delivered files nor in the runtime"))
            elif isinstance(node, ast.Attribute):
                referenced_attrs.add(node.attr)

        # Variables bound to instances of plan classes: x = Cls(...), self.x = Cls(...)
        var_type: Dict[str, Optional[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                    and isinstance(node.value.func, ast.Name) and node.value.func.id in local_classes:
                cls = local_classes[node.value.func.id]
                for t in node.targets:
                    key = t.id if isinstance(t, ast.Name) else (
                        f"self.{t.attr}" if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                        and t.value.id == "self" else None)
                    if key:
                        # Bound to two different classes → unknown
                        var_type[key] = cls if var_type.get(key, cls) == cls else None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
                continue
            n_pos, kw = len(node.args), {k.arg for k in node.keywords}
            func = node.func

            if isinstance(func, ast.Name) and func.id in local_classes:
                info = classes[local_classes[func.id]]
                init = info.methods.get("__init__")
                if init and not info.opaque:
                    problem = init.accepts(n_pos, kw)
                    if problem:
                        findings.append(Finding("error", 1, fname, node.lineno,
                            f"`{func.id}(...)` {problem[0]} (firma en `{info.module}.py`)",
                            en=f"`{func.id}(...)` {problem[1]} (signature in `{info.module}.py`)"))
            elif isinstance(func, ast.Name) and func.id in local_funcs:
                problem = functions[local_funcs[func.id]].accepts(n_pos, kw)
                if problem:
                    findings.append(Finding("error", 1, fname, node.lineno, f"`{func.id}(...)` {problem[0]}",
                                            en=f"`{func.id}(...)` {problem[1]}"))
            elif isinstance(func, ast.Attribute):
                owner = func.value
                key = owner.id if isinstance(owner, ast.Name) else (
                    f"self.{owner.attr}" if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name)
                    and owner.value.id == "self" else None)
                cls = var_type.get(key) if key else None
                # Chained on the constructor itself: Player(1, 2).shoot(3)
                if not cls and isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) \
                        and owner.func.id in local_classes:
                    cls, key = local_classes[owner.func.id], f"{owner.func.id}(...)"
                if not cls:
                    continue
                info = classes[cls]
                if info.opaque:
                    continue
                sig = info.methods.get(func.attr)
                if sig is None:
                    if func.attr not in info.attrs:
                        findings.append(Finding("error", 1, fname, node.lineno,
                            f"`{key}.{func.attr}(...)`: `{info.name}` (en `{info.module}.py`) no tiene el método `{func.attr}`",
                            en=f"`{key}.{func.attr}(...)`: `{info.name}` (in `{info.module}.py`) has no method `{func.attr}`"))
                    continue
                problem = sig.accepts(n_pos, kw)
                if problem:
                    findings.append(Finding("error", 1, fname, node.lineno,
                        f"`{key}.{func.attr}(...)` {problem[0]} (firma de `{info.name}.{func.attr}` en `{info.module}.py`)",
                        en=f"`{key}.{func.attr}(...)` {problem[1]} (signature of `{info.name}.{func.attr}` in `{info.module}.py`)"))

    # Public methods nobody calls anywhere in the set
    for key, info in classes.items():
        for name in info.methods:
            if name.startswith("_") or name in referenced_attrs:
                continue
            findings.append(Finding("warning", 1, f"{info.module}.py", info.line,
                f"`{info.name}.{name}()` no se usa en ningún archivo — comportamiento definido pero no conectado",
                en=f"`{info.name}.{name}()` is not used in any file: behavior defined but not connected"))

    # README pointing at files that don't exist
    for fname, src in files.items():
        if fname.lower().startswith("readme"):
            for ref in sorted(set(re.findall(r"[\w./-]+\.py\b", src))):
                if os.path.basename(ref) not in files:
                    findings.append(Finding("warning", 1, fname, None,
                        f"menciona `{ref}`, que no está entre los archivos entregados",
                        en=f"mentions `{ref}`, which is not among the delivered files"))

    entry = infer_entry_point(trees) if trees else None
    return findings, entry


# ── Layer 2: execution in the sandbox ──────────────────────────

def _imports_any(files: Dict[str, str], names: Set[str]) -> bool:
    for fname, src in files.items():
        if not fname.endswith(".py"):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] in names for a in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in names:
                return True
    return False


def _traceback_parts(stderr: str, lines: int = 6) -> Tuple[str, Optional[str]]:
    """(the last line, which names the failure; the frames before it, or None)."""
    tail = [l.strip() for l in stderr.strip().splitlines() if l.strip()][-lines:]
    if not tail:
        return "", None
    return tail[-1], "\n".join(tail[:-1]) or None


async def execution_findings(files: Dict[str, str], entry_point: str) -> Tuple[List[Finding], bool, Optional[str]]:
    """Run the entry point in the sandbox with a domain adapter.
    Returns (findings, ran, skipped_reason)."""
    from abi_core.common.sandbox import (
        SANDBOX_IMAGE_PYGAME, SANDBOX_IMAGE_PYTHON, SandboxLimits, run_in_sandbox,
    )

    payload = {k: v.encode() for k, v in files.items() if k.endswith(".py")}
    limits = SandboxLimits(timeout_s=LAYER2_TIMEOUT_S)

    if _imports_any(files, {"pygame"}):
        image = SANDBOX_IMAGE_PYGAME
        env = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "PYTHONHASHSEED": "0"}
        long_running = True      # a game loop never ends on its own
    else:
        image = SANDBOX_IMAGE_PYTHON
        env = {"PYTHONHASHSEED": "0"}
        long_running = False

    # One retry on an infrastructure failure (the sandbox itself, not the
    # code): live 2026-10-05 a run didn't return within its budget, then the
    # same files ran fine 3/3 minutes later. Root cause not established.
    result = await run_in_sandbox(payload, ["python", entry_point], image=image, env=env, limits=limits)
    # A policy denial (sandbox-service) is not an infrastructure failure:
    # asking again gets the same answer.
    if result.error and not result.error.startswith("sandbox denied"):
        result = await run_in_sandbox(payload, ["python", entry_point], image=image, env=env, limits=limits)
    if result.error:
        return [], False, f"no se pudo ejecutar: {result.error}"

    findings: List[Finding] = []
    if result.oom_killed:
        findings.append(Finding("error", 2, entry_point, None, "se quedó sin memoria al ejecutarse",
                                en="ran out of memory while running"))
    elif "Traceback (most recent call last)" in result.stderr:
        failure, frames = _traceback_parts(result.stderr)
        if "EOFError" in f"{failure} {frames}" and not long_running:
            findings.append(Finding("warning", 2, entry_point, None,
                f"espera entrada interactiva del usuario; no se pudo ejecutar sin ella ({failure})", frames,
                en=f"waits for interactive input from the user; it could not run without it ({failure})"))
        else:
            findings.append(Finding("error", 2, entry_point, None, f"falla al ejecutarse: {failure}", frames,
                                    en=f"fails when run: {failure}"))
    elif result.timed_out and not long_running:
        findings.append(Finding("warning", 2, entry_point, None,
            f"no terminó en {LAYER2_TIMEOUT_S}s (puede estar esperando entrada o en un ciclo)",
            en=f"did not end in {LAYER2_TIMEOUT_S}s (it may be waiting for input or in a loop)"))
    elif not result.timed_out and result.exit_code not in (0, None):
        failure, frames = _traceback_parts(result.stderr)
        findings.append(Finding("warning", 2, entry_point, None,
            f"terminó con código {result.exit_code}: {failure or result.stdout[-200:]}", frames,
            en=f"ended with code {result.exit_code}: {failure or result.stdout[-200:]}"))
    return findings, True, None


async def review_files(files: Dict[str, str], run_sandbox: bool = True) -> Optional[IntegrationReport]:
    """Full review. None when there is nothing to integrate (< 2 .py files)."""
    if sum(1 for f in files if f.endswith(".py")) < 2:
        return None
    findings, entry = static_findings(files)
    report = IntegrationReport(entry_point=entry, findings=findings)

    syntax_broken = any(f.layer == 1 and f.message.startswith("error de sintaxis") for f in findings)
    if not run_sandbox:
        report.layer2_skipped = "desactivada"
    elif not entry:
        report.layer2_skipped = "no se identificó el punto de entrada"
    elif syntax_broken:
        report.layer2_skipped = "hay errores de sintaxis"
    else:
        layer2, ran, skipped = await execution_findings(files, entry)
        report.findings += layer2
        report.layer2_ran = ran
        report.layer2_skipped = skipped
    return report


# ── Web deliverables: the page in a browser ────────────────────
# Spec: .abi/specs/not-implemented/web-deliverable-browser-check.md

_FRAME = re.compile(r"\(?([^\s()]+):(\d+):\d+\)?\s*$", re.M)
_MAX_WEB_ERRORS = 10
_MAX_EXTERNAL_NAMED = 3
_MAX_WEB_TEXT = 500


def web_entry_point(files: Dict[str, bytes]) -> Optional[str]:
    """index.html, or the only page. By code, never the model's choice."""
    pages = sorted(f for f in files if f.lower().endswith((".html", ".htm")))
    for page in pages:
        if page.lower() == "index.html":
            return page
    return pages[0] if len(pages) == 1 else None


def _web_findings(data: dict, entry_point: str) -> List[Finding]:
    """The check's result, deduplicated: a game loop repeats an error every frame."""
    findings: List[Finding] = []
    if data.get("crashed"):
        findings.append(Finding("error", 2, entry_point, None, "la página se cayó en el navegador",
                                en="the page crashed in the browser"))
    if data.get("load_timeout"):
        findings.append(Finding("error", 2, entry_point, None, "la página no terminó de cargar en el navegador",
                                en="the page did not finish loading in the browser"))
    for path in sorted({str(p)[:_MAX_WEB_TEXT] for p in data.get("missing") or []}):
        findings.append(Finding("error", 2, path, None, "la página pide este archivo y no existe",
                                en="the page asks for this file and it does not exist"))
    seen = set()
    for error in data.get("js_errors") or []:
        message = str(error.get("message", ""))[:_MAX_WEB_TEXT]
        if message in seen or len(seen) >= _MAX_WEB_ERRORS:
            continue
        seen.add(message)
        stack = str(error.get("stack") or "")
        frames = "\n".join(line.strip() for line in stack.splitlines()[1:7]) or None
        frame = _FRAME.search(stack)
        findings.append(Finding("error", 2, frame.group(1) if frame else entry_point,
                                int(frame.group(2)) if frame else None,
                                f"error de JavaScript: {message}", frames, en=f"JavaScript error: {message}"))
    return findings


async def web_execution_findings(files: Dict[str, bytes], entry_point: str) -> Tuple[List[Finding], bool, Optional[str]]:
    """Open the page in the browser sandbox. Returns (findings, ran, skipped_reason).
    The check failing is never the page's fault: it leaves the page unverified."""
    from abi_core.common.sandbox import SANDBOX_IMAGE_BROWSER, SandboxLimits, run_in_sandbox

    limits = SandboxLimits(timeout_s=WEB_CHECK_TIMEOUT_S, memory_mb=WEB_CHECK_MEMORY_MB, pids=WEB_CHECK_PIDS)
    command = ["python", "/opt/abi-sandbox/browser_check.py", entry_point]
    try:
        result = await run_in_sandbox(files, command, image=SANDBOX_IMAGE_BROWSER, limits=limits)
        if result.error and not result.error.startswith("sandbox denied"):
            result = await run_in_sandbox(files, command, image=SANDBOX_IMAGE_BROWSER, limits=limits)
    except ValueError as e:  # too large, or a file name the bundle refuses
        return [], False, f"{_COULD_NOT_RUN}: {e}"
    if result.error:
        return [], False, f"{_COULD_NOT_RUN}: {result.error}"
    try:
        data = json.loads(result.result_json or "")
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        why = "no terminó a tiempo" if result.timed_out else "sin memoria" if result.oom_killed else "sin resultado"
        return [], False, f"{_COULD_NOT_RUN}: {why}"

    findings = _web_findings(data, entry_point)
    external = sorted({str(u)[:_MAX_WEB_TEXT] for u in data.get("external") or []})
    if external:
        # With the resource refused, its absence breaks the page here even if
        # it works for the user: only what doesn't depend on it is a finding.
        named = ", ".join(external[:_MAX_EXTERNAL_NAMED])
        more = len(external) - _MAX_EXTERNAL_NAMED
        kept = [f for f in findings if f.message.startswith("la página pide")]
        return kept, False, f"{_EXTERNAL}: {named}" + (f" (+{more})" if more > 0 else "")
    return findings, True, None


async def review_web_files(files: Dict[str, bytes], run_sandbox: bool = True) -> Optional[IntegrationReport]:
    """The page checked in a browser. None when the set has no page."""
    if not any(f.lower().endswith((".html", ".htm")) for f in files):
        return None
    entry = web_entry_point(files)
    report = IntegrationReport(entry_point=entry, web=True)
    if not run_sandbox:
        report.layer2_skipped = "desactivada"
    elif not entry:
        report.layer2_skipped = "no se identificó el punto de entrada"
    else:
        report.findings, report.layer2_ran, report.layer2_skipped = await web_execution_findings(files, entry)
    return report
