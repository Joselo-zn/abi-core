"""
Parsing of the reviewer's questions. Its prompts (role, questions call and
their text renderings) live in abi_core.common.prompts.reviewer and are
re-exported here.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/04-ephemeral-prompts.md,
.abi/specs/implemented/prompts-single-location.md
"""

import json
import re
from typing import Dict, List, Optional
from abi_core.common.prompts.reviewer import (  # noqa: F401  (moved; re-exported)
    build_reviewer_questions_prompt,
    files_with_specs_text,
    plan_and_design_text,
    REVIEWER_QUESTIONS,
    REVIEWER_ROLE,
    spec_text,
    specs_text,
)

_QUESTIONS_RE = re.compile(
    r"^=== QUESTIONS: (?P<name>[\w./-]+) ===\n(?P<body>.*?)^=== END QUESTIONS ===$", re.M | re.S
)
_NUMBERED = re.compile(r"^\s*\d+[.)]\s*(?P<q>.+?)\s*$")


def parse_questions(text: str, allowed: set, max_per_agent: int = 5) -> Dict[str, List[str]]:
    """{filename: [questions]} for files whose agent can be asked; capped by
    code, whatever the model wrote."""
    out: Dict[str, List[str]] = {}
    for m in _QUESTIONS_RE.finditer(text or ""):
        name = m.group("name")
        if name not in allowed:
            continue
        qs = [q.group("q") for q in map(_NUMBERED.match, m.group("body").splitlines()) if q]
        if qs:
            out.setdefault(name, [])
            out[name] = (out[name] + qs)[:max_per_agent]
    return out
