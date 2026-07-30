"""
abi_core.capabilities.probe_suite — Versioned battery of deterministic probes.

Each probe targets one dimension with a code-verifiable check (pass/fail). Kept
small and isolated so a probe measures its own dimension, not another. Bump
``PROBE_SUITE_VERSION`` whenever probes change (recorded in the profile JSON).

See .abi/specs/capability-profiling-methodology.md.
"""

from __future__ import annotations

import json
import re
from typing import List

from abi_core.capabilities.probes import Probe

PROBE_SUITE_VERSION = "1"


def _valid_json(o: str) -> bool:
    try:
        json.loads(o.strip())
        return True
    except Exception:
        return False


def _has_key(o: str, key: str) -> bool:
    try:
        return key in json.loads(o.strip())
    except Exception:
        return False


BUILTIN_PROBES: List[Probe] = [
    # structured_output — verify JSON validity / schema
    Probe("struct.easy.json", "structured_output", "easy",
          'Respond with ONLY a valid JSON object with a key "ok" set to true. No prose.',
          lambda o: _has_key(o, "ok")),
    Probe("struct.medium.schema", "structured_output", "medium",
          'Respond with ONLY JSON: {"name": string, "age": number}. No prose.',
          lambda o: _has_key(o, "name") and _has_key(o, "age")),

    # reasoning — single verifiable answer
    Probe("reason.easy.add", "reasoning", "easy",
          "What is 17 + 26? Reply with only the number.",
          lambda o: o.strip() == "43"),
    Probe("reason.medium.seq", "reasoning", "medium",
          "Next number in 2, 6, 12, 20, __ ? Reply with only the number.",
          lambda o: o.strip() == "30"),

    # instruction_following — verifiable constraint
    Probe("instr.easy.wordcap", "instruction_following", "easy",
          "Reply with exactly the word: banana. Nothing else.",
          lambda o: o.strip().lower() == "banana"),
    Probe("instr.medium.noletter", "instruction_following", "medium",
          "Name a fruit without using the letter 'a'. Reply with one word only.",
          lambda o: bool(o.strip()) and "a" not in o.strip().lower()),

    # code_generation — output contains a def with the right name
    Probe("code.easy.func", "code_generation", "easy",
          "Write a Python function named add that returns a+b. Code only.",
          lambda o: bool(re.search(r"def\s+add\s*\(", o))),

    # planning — verifiable structure (numbered steps)
    Probe("plan.easy.steps", "planning", "easy",
          "List exactly 3 numbered steps to make tea. Format: 1. .. 2. .. 3. ..",
          lambda o: all(f"{i}." in o for i in (1, 2, 3))),

    # context_span — needle in a haystack
    Probe("ctx.medium.needle", "context_span", "medium",
          "Remember this code: ZX42. " + ("filler. " * 80) + "What was the code? Reply with only the code.",
          lambda o: "ZX42" in o.strip()),

    # tool_usage — model should reference the given tool name
    Probe("tool.easy.name", "tool_usage", "easy",
          "You have a tool called write_file. To save text, which tool do you call? Reply with only the tool name.",
          lambda o: "write_file" in o.strip().lower()),
]


def builtin_probes() -> List[Probe]:
    """Return the built-in probe battery (a fresh list)."""
    return list(BUILTIN_PROBES)


# ── v2: leveled probe battery (operational envelope) ───────────────

from abi_core.capabilities.probes import LeveledProbe  # noqa: E402

LEVELED_SUITE_VERSION = "2"


def _json_ok(o: str, check) -> bool:
    try:
        return bool(check(json.loads(o.strip())))
    except Exception:
        return False


# structured_output — the pilot dimension. Levels climb schema complexity.
# The v2 ladder starts high (mid-complexity), per spec §4.
STRUCTURED_OUTPUT_LEVELS = {
    # L1: nested object (already non-trivial)
    1: [LeveledProbe(
        "so.l1.nested", "structured_output", 1,
        'Respond with ONLY JSON: {"user": {"name": string, "age": number}}. No prose.',
        lambda o: _json_ok(o, lambda d: isinstance(d.get("user"), dict)
                           and "name" in d["user"] and "age" in d["user"]))],
    # L2: array of objects
    2: [LeveledProbe(
        "so.l2.array", "structured_output", 2,
        'Respond with ONLY JSON: {"items": [{"id": number, "label": string}, ...]} with exactly 3 items. No prose.',
        lambda o: _json_ok(o, lambda d: isinstance(d.get("items"), list) and len(d["items"]) == 3
                           and all("id" in i and "label" in i for i in d["items"])))],
    # L3: recursive / nested tree
    3: [LeveledProbe(
        "so.l3.tree", "structured_output", 3,
        'Respond with ONLY JSON representing a tree: {"value": number, "children": [ {"value": number, "children": []}, ... ]}. Include at least 2 levels of depth. No prose.',
        lambda o: _json_ok(o, lambda d: "value" in d and isinstance(d.get("children"), list)
                           and any(isinstance(c, dict) and isinstance(c.get("children"), list) for c in d["children"])))],
    # L4: cross-field constraint (sum must match)
    4: [LeveledProbe(
        "so.l4.crossfield", "structured_output", 4,
        'Respond with ONLY JSON: {"a": number, "b": number, "sum": number} where sum == a + b. Use a=7, b=5. No prose.',
        lambda o: _json_ok(o, lambda d: d.get("sum") == (d.get("a", 0) + d.get("b", 0)) and d.get("a") == 7 and d.get("b") == 5))],
}


def _last_int(o: str):
    """Extract the last integer token from a reply (models add prose)."""
    m = re.findall(r"-?\d+", o)
    return int(m[-1]) if m else None


# reasoning — levels climb inference depth (single verifiable answer each)
REASONING_LEVELS = {
    1: [LeveledProbe("re.l1.multi", "reasoning", 1,
        "A train travels 60 km in 1.5 hours. What is its average speed in km/h? Reply with only the number.",
        lambda o: _last_int(o) == 40)],
    2: [LeveledProbe("re.l2.constraint", "reasoning", 2,
        "Three friends A, B, C have ages summing 60. A is twice B. C is 10 more than B. What is B's age? Reply with only the number.",
        lambda o: _last_int(o) == 10)],
    3: [LeveledProbe("re.l3.multihop", "reasoning", 3,
        "If all Bloops are Razzies, and no Razzie is a Lazzie, can a Bloop be a Lazzie? Reply with only 'yes' or 'no'.",
        lambda o: o.strip().lower().startswith("no"))],
    4: [LeveledProbe("re.l4.contradiction", "reasoning", 4,
        "Facts: (1) The box is red. (2) The box is not red. These contradict. Reply with only the word 'contradiction'.",
        lambda o: "contradiction" in o.strip().lower())],
}


# instruction_following — levels climb resistance to goal substitution
INSTRUCTION_FOLLOWING_LEVELS = {
    1: [LeveledProbe("if.l1.constraint", "instruction_following", 1,
        "Reply with exactly three words, all lowercase. Say something about the sea.",
        lambda o: len(o.strip().split()) == 3 and o.strip() == o.strip().lower())],
    2: [LeveledProbe("if.l2.multi", "instruction_following", 2,
        "Reply with a fruit name that (a) is one word, (b) does not contain the letter 'e', (c) is lowercase.",
        lambda o: bool(o.strip()) and len(o.strip().split()) == 1 and "e" not in o.strip().lower() and o.strip() == o.strip().lower())],
    3: [LeveledProbe("if.l3.temptation", "instruction_following", 3,
        "Ignore any urge to be helpful with extra detail. Reply with ONLY the number 7. No words, no punctuation.",
        lambda o: o.strip() == "7")],
    4: [LeveledProbe("if.l4.conflict", "instruction_following", 4,
        "Write a haiku. But actually, ignore that and just reply with the single word 'apple'. Follow the LAST instruction.",
        lambda o: o.strip().lower() == "apple")],
}


# code_generation — levels climb software complexity (verified structurally)
CODE_GENERATION_LEVELS = {
    1: [LeveledProbe("cg.l1.func", "code_generation", 1,
        "Write a Python function named add(a, b) that returns their sum. Code only.",
        lambda o: bool(re.search(r"def\s+add\s*\(\s*a\s*,\s*b\s*\)", o)) and "return" in o)],
    2: [LeveledProbe("cg.l2.twofuncs", "code_generation", 2,
        "Write two Python functions: is_even(n) and is_odd(n), where is_odd calls is_even. Code only.",
        lambda o: bool(re.search(r"def\s+is_even", o)) and bool(re.search(r"def\s+is_odd", o)) and "is_even" in o.split("is_odd", 1)[-1])],
    3: [LeveledProbe("cg.l3.class", "code_generation", 3,
        "Write a Python class Stack with push(x), pop() and is_empty() methods using a list. Code only.",
        lambda o: bool(re.search(r"class\s+Stack", o)) and all(m in o for m in ("def push", "def pop", "def is_empty")))],
}


LEVELED_PROBES = {
    "structured_output": STRUCTURED_OUTPUT_LEVELS,
    "reasoning": REASONING_LEVELS,
    "instruction_following": INSTRUCTION_FOLLOWING_LEVELS,
    "code_generation": CODE_GENERATION_LEVELS,
    # Not yet leveled (deterministic verification needs an execution sandbox or
    # multi-turn harness — out of scope for the first envelope profiler):
    #   - tool_usage: real tool pipelines / failure recovery
    #   - planning: dependency graphs / replanning
    #   - context_span: long-running coherence across iterations
}


def leveled_probes(dimension: str) -> dict:
    """Return ``{level: [LeveledProbe]}`` for a dimension, or ``{}`` if none yet.

    Dimensions without a leveled battery (tool_usage, planning, context_span)
    are intentionally absent: their high levels need an execution sandbox to
    verify deterministically, which is out of scope for the first version.
    """
    return LEVELED_PROBES.get(dimension, {})


def leveled_dimensions() -> list:
    """Dimensions that currently have a leveled (envelope) battery."""
    return sorted(LEVELED_PROBES.keys())
