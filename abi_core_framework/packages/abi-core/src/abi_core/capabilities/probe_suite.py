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
