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
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Third-party modules the sandbox images provide (sandbox-images/).
SANDBOX_THIRD_PARTY = {"pygame", "numpy"}

LAYER2_TIMEOUT_S = int(os.getenv("INTEGRATION_REVIEW_RUN_SECONDS", "15"))

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

    def as_text(self) -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"[{where}] {self.message}"


@dataclass
class IntegrationReport:
    entry_point: Optional[str]
    findings: List[Finding] = field(default_factory=list)
    layer2_ran: bool = False
    layer2_skipped: Optional[str] = None

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

    def as_text(self) -> str:
        """Deterministic, user-facing report (Spanish, like the rest of the
        Orchestrator's deterministic messages)."""
        lines = ["**Revisión de integración de los archivos entregados**"]
        if self.entry_point:
            lines.append(f"Punto de entrada: `{self.entry_point}`")
        if self.layer2_ran:
            lines.append("Ejecución en sandbox: sí")
        elif self.layer2_skipped:
            lines.append(f"Ejecución en sandbox: no ({self.layer2_skipped})")
        if self.errors:
            lines.append(f"\n❌ {len(self.errors)} error(es) — el conjunto no funciona tal como se entregó:")
            lines += [f"- {f.as_text()}" for f in self.errors]
        elif self.execution_unverified:
            lines.append(
                "\n⚠️ Sin verificar: la revisión estática no encontró errores, pero el conjunto "
                "no se pudo ejecutar, así que no está comprobado que funcione."
            )
        if self.warnings:
            lines.append(f"\n⚠️ {len(self.warnings)} advertencia(s):")
            lines += [f"- {f.as_text()}" for f in self.warnings]
        if not self.errors and not self.warnings and not self.execution_unverified:
            lines.append("\n✅ Sin hallazgos.")
        return "\n".join(lines)

    def as_pass_text(self) -> str:
        """Deterministic verdict for a set that passed (no errors, not
        unverified), saying exactly what the check covered — so the user's
        answer never depends on a model interpreting the review. Live
        2026-10-15: the synthesis model reported a set with 0 errors as "does
        not run" (from unused-method warnings) and another as "fully
        functional". Spanish, like as_text()."""
        entry = f"`{self.entry_point}`" if self.entry_point else "el punto de entrada"
        if self.layer2_ran:
            lines = [
                f"✅ Verificado por código: los archivos encajan entre sí y {entry} se ejecutó "
                f"en el sandbox hasta {LAYER2_TIMEOUT_S} s sin errores. Eso no prueba el uso real "
                "(por ejemplo, que un juego se pueda jugar bien)."
            ]
            warnings_header = f"⚠️ {len(self.warnings)} advertencia(s), que no impiden que se ejecute:"
        else:
            lines = [
                "✅ Revisión estática sin errores: los archivos encajan entre sí. "
                f"No se ejecutaron ({self.layer2_skipped or 'sin ejecución'})."
            ]
            warnings_header = f"⚠️ {len(self.warnings)} advertencia(s):"
        if self.warnings:
            lines.append("\n" + warnings_header)
            lines += [f"- {f.as_text()}" for f in self.warnings]
        return "\n".join(lines)


# ── Layer 1: static ────────────────────────────────────────────

@dataclass
class _Sig:
    min_args: int
    max_args: Optional[int]   # None = *args
    kw_names: Set[str]
    any_kwargs: bool

    def accepts(self, n_pos: int, kw: Set[str]) -> Optional[str]:
        if self.max_args is not None and n_pos > self.max_args:
            return f"recibe {n_pos} argumento(s) posicional(es), acepta como máximo {self.max_args}"
        unknown = {k for k in kw if k not in self.kw_names} if not self.any_kwargs else set()
        if unknown:
            return f"argumento(s) con nombre desconocido(s): {', '.join(sorted(unknown))}"
        provided = n_pos + len(kw & self.kw_names)
        if provided < self.min_args:
            return f"recibe {provided} argumento(s), requiere al menos {self.min_args}"
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
            findings.append(Finding("error", 1, fname, e.lineno, f"error de sintaxis: {e.msg}"))

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
                                f"`from {top} import {alias.name}`: `{modules[top]}` no define `{alias.name}`"))
                        else:
                            bound = alias.asname or alias.name
                            if f"{top}.{alias.name}" in classes:
                                local_classes[bound] = f"{top}.{alias.name}"
                            if f"{top}.{alias.name}" in functions:
                                local_funcs[bound] = f"{top}.{alias.name}"
                elif top not in sys.stdlib_module_names and top not in SANDBOX_THIRD_PARTY:
                    findings.append(Finding("warning", 1, fname, node.lineno,
                        f"importa `{node.module}`, que no está entre los archivos entregados ni en el entorno de ejecución"))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in modules and top not in sys.stdlib_module_names and top not in SANDBOX_THIRD_PARTY:
                        findings.append(Finding("warning", 1, fname, node.lineno,
                            f"importa `{alias.name}`, que no está entre los archivos entregados ni en el entorno de ejecución"))
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
                            f"`{func.id}(...)` {problem} (firma en `{info.module}.py`)"))
            elif isinstance(func, ast.Name) and func.id in local_funcs:
                problem = functions[local_funcs[func.id]].accepts(n_pos, kw)
                if problem:
                    findings.append(Finding("error", 1, fname, node.lineno, f"`{func.id}(...)` {problem}"))
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
                            f"`{key}.{func.attr}(...)`: `{info.name}` (en `{info.module}.py`) no tiene el método `{func.attr}`"))
                    continue
                problem = sig.accepts(n_pos, kw)
                if problem:
                    findings.append(Finding("error", 1, fname, node.lineno,
                        f"`{key}.{func.attr}(...)` {problem} (firma de `{info.name}.{func.attr}` en `{info.module}.py`)"))

    # Public methods nobody calls anywhere in the set
    for key, info in classes.items():
        for name in info.methods:
            if name.startswith("_") or name in referenced_attrs:
                continue
            findings.append(Finding("warning", 1, f"{info.module}.py", info.line,
                f"`{info.name}.{name}()` no se usa en ningún archivo — comportamiento definido pero no conectado"))

    # README pointing at files that don't exist
    for fname, src in files.items():
        if fname.lower().startswith("readme"):
            for ref in sorted(set(re.findall(r"[\w./-]+\.py\b", src))):
                if os.path.basename(ref) not in files:
                    findings.append(Finding("warning", 1, fname, None,
                        f"menciona `{ref}`, que no está entre los archivos entregados"))

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


def _traceback_tail(stderr: str, lines: int = 6) -> str:
    tail = [l for l in stderr.strip().splitlines() if l.strip()][-lines:]
    return " ⏎ ".join(l.strip() for l in tail)


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
        findings.append(Finding("error", 2, entry_point, None, "se quedó sin memoria al ejecutarse"))
    elif "Traceback (most recent call last)" in result.stderr:
        tail = _traceback_tail(result.stderr)
        if "EOFError" in tail and not long_running:
            findings.append(Finding("warning", 2, entry_point, None,
                f"espera entrada interactiva del usuario; no se pudo ejecutar sin ella ({tail})"))
        else:
            findings.append(Finding("error", 2, entry_point, None, f"falla al ejecutarse: {tail}"))
    elif result.timed_out and not long_running:
        findings.append(Finding("warning", 2, entry_point, None,
            f"no terminó en {LAYER2_TIMEOUT_S}s (puede estar esperando entrada o en un ciclo)"))
    elif not result.timed_out and result.exit_code not in (0, None):
        findings.append(Finding("warning", 2, entry_point, None,
            f"terminó con código {result.exit_code}: {_traceback_tail(result.stderr) or result.stdout[-200:]}"))
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
