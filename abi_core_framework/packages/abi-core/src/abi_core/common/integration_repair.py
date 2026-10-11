"""
Integration repair — rewrite a set of files that don't work together, in ONE
model call.

No tool loop: the files go inline in the prompt, the model returns every
file between fixed markers, and code parses them. Live 2026-10-05 the same
model (qwen3-coder:30b) inside a tool-calling loop called read_file 21 times
without ever writing a file; given the files inline in a single call, it
returned a set that passed the integration review in one round (~4 min).
The membrane stays deterministic: bounded input (the delivered files + a
verified report), one call, output parsed by code, judged again by the
integration review — never by the model itself.

Spec: .abi/specs/not-implemented/sdd-pipeline/07-deliverable-integration-review.md
Case study: .abi/casos de estudio/2026-10-05-limites-del-no-determinismo-coherencia-sin-conversacion.md
"""

import ast
import builtins
import re
from typing import Dict, List, Optional, Tuple

from abi_core.common.utils import abi_logging
from abi_core.common.prompts.reviewer import build_repair_prompt  # noqa: F401  (moved; re-exported)

_FILE_RE = re.compile(
    r"^=== FILE: (?P<name>[\w./-]+) ===\n(?P<body>.*?)^=== END FILE ===$", re.M | re.S
)
_CHANGES_RE = re.compile(r"^=== CHANGES ===\n(?P<body>.*?)^=== END CHANGES ===$", re.M | re.S)


def allowed_imports(plan: dict, filenames) -> Dict[str, List[str]]:
    """{file: [files it may import]} for the delivered .py files.

    From the plan's technical design when it has one (each file's
    `depends_on`, filenames already), else from the tasks' dependencies
    (task ids or, as seen live 2026-10-06, filenames). Empty dict when the
    plan gives nothing usable."""
    py = {f for f in filenames if f.endswith(".py")}
    design = ((plan or {}).get("technical_design") or {}).get("files") or []
    allowed = {}
    if design:
        for f in design:
            name = f.get("filename")
            if name in py:
                allowed[name] = sorted({d for d in f.get("depends_on") or [] if d in py and d != name})
    else:
        tasks = (plan or {}).get("tasks", [])
        tag_of = {t.get("task_id"): (t.get("target") or {}).get("tag") for t in tasks}
        for t in tasks:
            tag = (t.get("target") or {}).get("tag")
            if tag not in py:
                continue
            deps = [tag_of.get(d, d) for d in t.get("dependencies", [])]
            allowed[tag] = sorted({d for d in deps if d in py and d != tag})
    return allowed if len(allowed) >= 2 else {}


def parse_repaired_files(text: str, allowed: set) -> Dict[str, str]:
    """Files between markers, only for names that were delivered (the model
    may not add or rename files). Content gets a trailing newline."""
    out = {}
    for m in _FILE_RE.finditer(text or ""):
        name = m.group("name")
        if name in allowed:
            out[name] = m.group("body").rstrip("\n") + "\n"
    return out


def parse_changes(text: str, allowed: set) -> Dict[str, str]:
    """{filename: why} from the CHANGES section, only for files of the set."""
    m = _CHANGES_RE.search(text or "")
    out = {}
    for line in (m.group("body") if m else "").splitlines():
        name, sep, why = line.partition(":")
        if sep and name.strip() in allowed:
            out[name.strip()] = why.strip()
    return out


def _bound_names(tree: ast.Module) -> set:
    """Every name bound anywhere in a module (conservative on purpose)."""
    bound = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
    return bound


def _imports_module(tree: ast.Module, module: str) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == module:
            return True
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] == module for a in n.names):
            return True
    return False


def fix_missing_imports(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Add `from x import Name` where a file uses a name it never binds and
    exactly one other file of the set defines it at module level.

    Deterministic and conservative: skipped when two files define the name,
    when the file binds it anywhere, or when the import would be circular
    (the owner already imports this file). Live 2026-10-06 a repair left
    game.py using Player without importing it.
    """
    trees = {}
    for name, src in files.items():
        if name.endswith(".py"):
            try:
                trees[name] = ast.parse(src)
            except SyntaxError:
                pass
    defs = {
        name[:-3]: {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        for name, t in trees.items()
    }
    fixed, notes = dict(files), []
    for name, tree in trees.items():
        module = name[:-3]
        bound = _bound_names(tree) | set(dir(builtins))
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        adds = []
        for missing in sorted(used - bound):
            owners = [m for m, d in defs.items() if m != module and missing in d]
            if len(owners) != 1:
                continue
            owner = owners[0]
            if _imports_module(trees[owner + ".py"], module):
                notes.append(f"{name}: '{missing}' is defined in {owner}.py, which imports {module} — circular, not added")
                continue
            adds.append(f"from {owner} import {missing}")
        if adds:
            lines = files[name].splitlines(keepends=True)
            last = max((n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
            lines[last:last] = [a + "\n" for a in adds]
            fixed[name] = "".join(lines)
            notes += [f"{name}: added `{a}`" for a in adds]
    return fixed, notes


async def repair_files(
    files: Dict[str, str],
    entry_point: Optional[str],
    report_text: str,
    llm_config: dict,
    call_timeout: float = 2400,
    allowed_imports: Optional[Dict[str, List[str]]] = None,
    *,
    system_prompt: Optional[str] = None,
    answers: Optional[str] = None,
    missing: Optional[List[str]] = None,
    plan_and_design: Optional[str] = None,
    specs: Optional[str] = None,
    changes_out: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """One model call, then deterministic import fixes; returns
    {filename: new content} for files that changed (names in `files`, plus
    `missing` files it was asked to write). Empty dict if nothing changed.
    Pass `changes_out` (a dict) to get the model's CHANGES lines back."""
    from abi_core.agent.llm_provider import invoke

    want_changes = changes_out is not None
    prompt = build_repair_prompt(
        files, entry_point or "?", report_text, allowed_imports,
        answers=answers, missing=missing, plan_and_design=plan_and_design,
        specs=specs, want_changes=want_changes,
    )
    abi_logging(
        f"[🛠️] Integration repair: one call to {llm_config.get('model')} "
        f"with {len(files)} file(s), {len(prompt)} chars"
    )
    response = await invoke(llm_config, prompt, call_timeout=call_timeout, system_prompt=system_prompt)
    allowed = set(files) | set(missing or [])
    repaired = parse_repaired_files(response, allowed)
    if want_changes:
        changes_out.update(parse_changes(response, allowed))
    merged, notes = fix_missing_imports({**files, **repaired})
    for note in notes:
        abi_logging(f"[🛠️] Import fix: {note}")
    changed = {k: v for k, v in merged.items() if v != files.get(k)}
    abi_logging(
        f"[🛠️] Integration repair: model returned {sorted(repaired)}; changed {sorted(changed)}"
    )
    return changed
