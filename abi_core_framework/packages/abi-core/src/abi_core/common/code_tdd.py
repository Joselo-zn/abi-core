"""
Code agent TDD — the technical design document each code agent hands in
with its file.

Six fields. Four are extracted from the code (AST, deterministic); two are
written by the model in the same generation as the file:

    exposes             classes, methods, signatures, public functions
    assumes             what it imports from the plan's other files and
                        which methods it calls on their classes (with how
                        many arguments)
    role                program-level behaviour: own window, init, event
                        loop, render loop, __main__, work done at import
    resources           external files it loads (images, sounds, fonts,
                        open(...))
    purpose_data_model  (model) what the file does; what each shared
                        entity is and who owns it
    needed_not_found    (model) API it expected from other files and did
                        not find in their contracts

Plus `early_findings`: this file's "assumes" checked against the "exposes"
of the files it depends on (same logic as layer 1 of the integration
review, file by file). Recorded for the reviewer only — it triggers nothing.

Measured on 11 real multi-file runs (2026-10-02 → 2026-10-06): 31 errors of
an invented cross-file API, external files that don't exist in 4 runs,
modules carrying a whole program in 9. Spec:
.abi/specs/not-implemented/ephemeral-reviewer-pipeline/01-code-agent-tdd.md
"""

import ast
import os
import re
import sys
from typing import Dict, List, Optional
from abi_core.common.prompts.code_agent import (  # noqa: F401  (moved; re-exported)
    TDD_MARKER,
    TDD_PROMPT_INSTRUCTION,
    tdd_summary,
)

_PURPOSE_RE = re.compile(r"Purpose and data model:\s*(?P<v>.*?)(?=\n\s*Needed but not found:|\Z)", re.S | re.I)
_NEEDED_RE = re.compile(r"Needed but not found:\s*(?P<v>.*?)(?=\n\s*\n|\Z)", re.S | re.I)

# Calls that load a file from disk: (receiver attribute, method).
_RESOURCE_CALLS = {("image", "load"), ("mixer", "Sound"), ("font", "Font"), ("music", "load")}

# ── Deterministic fields ───────────────────────────────────────

def extract_exposes(source: str) -> Dict:
    """Same shape as context_loader.extract_python_contract."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    def _sig(node) -> str:
        return f"{node.name}({', '.join(a.arg for a in node.args.args)})"

    classes, functions = [], []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "methods": [
                _sig(i) for i in node.body if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))]})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "signature": _sig(node)})
    return {"classes": classes, "functions": functions}


def extract_assumes(source: str, plan_modules: List[str]) -> Dict:
    """What this file takes from the plan's other files.

    imports: {module: [names]} for `from <plan module> import ...` and
             `import <plan module>`;
    calls:   ["Class.method/N", "Class(N)"] — calls on objects whose class
             was imported from a plan module and is visible from an
             assignment (`p = Player(...)`, `self.p = Player(...)`), with N
             positional arguments. Same visibility limit as layer 1.
    missing_modules: modules imported that are neither plan files, stdlib
             nor installed third-party — e.g. an `assets` nobody delivered.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    plan = set(plan_modules)
    imports: Dict[str, List[str]] = {}
    imported_classes: Dict[str, str] = {}   # local name -> "module.Name"
    missing = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top = node.module.split(".")[0]
            if top in plan:
                names = [a.name for a in node.names]
                imports.setdefault(top, []).extend(n for n in names if n not in imports.get(top, []))
                for a in node.names:
                    imported_classes[a.asname or a.name] = f"{top}.{a.name}"
            elif not _is_known_module(top):
                missing.add(top)
        elif isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top in plan:
                    imports.setdefault(top, [])
                elif not _is_known_module(top):
                    missing.add(top)

    var_class: Dict[str, Optional[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and isinstance(node.value.func, ast.Name) and node.value.func.id in imported_classes:
            cls = imported_classes[node.value.func.id]
            for t in node.targets:
                key = t.id if isinstance(t, ast.Name) else (
                    f"self.{t.attr}" if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == "self" else None)
                if key:
                    var_class[key] = cls if var_class.get(key, cls) == cls else None

    calls = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        n = len(node.args)
        f = node.func
        if isinstance(f, ast.Name) and f.id in imported_classes:
            calls.add(f"{imported_classes[f.id].split('.', 1)[1]}({n})")
        elif isinstance(f, ast.Attribute):
            o = f.value
            key = o.id if isinstance(o, ast.Name) else (
                f"self.{o.attr}" if isinstance(o, ast.Attribute) and isinstance(o.value, ast.Name)
                and o.value.id == "self" else None)
            cls = var_class.get(key) if key else None
            if cls:
                calls.add(f"{cls.split('.', 1)[1]}.{f.attr}/{n}")

    return {"imports": imports, "calls": sorted(calls), "missing_modules": sorted(missing)}


def _is_known_module(name: str) -> bool:
    """Standard library or a third-party module the sandbox image provides.
    A fixed reference, the same as the integration review — not what happens
    to be installed where this runs (neither the Orchestrator nor the
    ephemeral image has pygame, the sandbox does)."""
    from abi_core.common.integration_review import SANDBOX_THIRD_PARTY
    return name in sys.stdlib_module_names or name in SANDBOX_THIRD_PARTY


def extract_role(source: str) -> Dict:
    """Program-level behaviour. A module (not the entry point) should not
    own a window, an event loop or a render loop — in 9 of 11 measured runs
    modules carried a whole program of their own."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    flags = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            owner = getattr(n.func.value, "attr", getattr(n.func.value, "id", ""))
            pair = (owner, n.func.attr)
            if pair == ("display", "set_mode"):
                flags.add("creates_window")
            elif pair == ("pygame", "init"):
                flags.add("initializes_pygame")
            elif pair == ("event", "get"):
                flags.add("handles_events")
            elif pair in (("display", "flip"), ("display", "update")):
                flags.add("render_loop")
        elif isinstance(n, ast.If) and isinstance(n.test, ast.Compare) \
                and getattr(n.test.left, "id", "") == "__name__":
            flags.add("has_main_guard")
    import_time = []
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) \
                and getattr(n.test.left, "id", "") == "__name__":
            continue
        if any(isinstance(x, ast.Call) for x in ast.walk(n)):
            import_time.append(ast.unparse(n)[:80])
    return {"flags": sorted(flags), "runs_at_import": import_time}


def extract_resources(source: str) -> List[str]:
    """External files the code loads. A string literal is reported as is;
    a computed path as '<computed>'."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        is_resource = (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute)
                       and (f.value.attr, f.attr) in _RESOURCE_CALLS) or \
                      (isinstance(f, ast.Name) and f.id == "open")
        if not is_resource or not n.args:
            continue
        a = n.args[0]
        if isinstance(a, ast.Constant) and a.value is None:
            continue  # font.Font(None, ...) is pygame's default font, not a file
        label = f.attr if isinstance(f, ast.Attribute) else "open"
        path = a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else "<computed>"
        out.append(f"{label}({path})")
    return sorted(set(out))


# ── Model fields ───────────────────────────────────────────────

def parse_model_fields(answer: str) -> Dict[str, Optional[str]]:
    """The two fields the model writes before its code, at the start of its
    answer (TDD_PROMPT_INSTRUCTION). Missing fields come back as None."""
    text = answer or ""
    i = text.find(TDD_MARKER)
    section = text[i + len(TDD_MARKER):] if i != -1 else ""
    purpose = _PURPOSE_RE.search(section)
    needed = _NEEDED_RE.search(section)
    clean = lambda m: (m.group("v").strip() or None) if m else None
    return {"purpose_data_model": clean(purpose), "needed_not_found": clean(needed)}


# ── The TDD ────────────────────────────────────────────────────

def build_tdd(filename: str, files: Dict[str, str], model_answer: str = "") -> Dict:
    """TDD for `filename`. `files` holds this file and every other .py the
    agent had in its workspace (its dependencies); they are the plan modules
    for "assumes" and the reference for early findings."""
    from abi_core.common.integration_review import static_findings

    source = files.get(filename, "")
    plan_modules = [f[:-3] for f in files if f.endswith(".py") and f != filename]
    model = parse_model_fields(model_answer)

    # Early findings: layer 1 of the integration review over this file and
    # the files it can see; only errors that point at this file, and not the
    # "defined but unused" warnings (other files may use it later).
    findings, _ = static_findings({k: v for k, v in files.items() if k.endswith(".py")})
    early = [f.message for f in findings if f.file == filename and f.severity == "error"]

    return {
        "file": filename,
        "exposes": extract_exposes(source),
        "assumes": extract_assumes(source, plan_modules),
        "role": extract_role(source),
        "resources": extract_resources(source),
        "purpose_data_model": model["purpose_data_model"],
        "needed_not_found": model["needed_not_found"],
        "model_fields_missing": [k for k, v in model.items() if not v],
        "early_findings": early,
    }

