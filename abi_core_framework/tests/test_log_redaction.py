"""Logs carry no user content (spec: .abi/specs/not-implemented/logs-without-user-content.md).

redact() and mask_email(), a sentinel through a logging path, and a guard over
the source: an abi_logging f-string must not interpolate a user-content
variable outside redact()/mask_email().
"""

import ast
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from abi_core.common.utils import mask_email, redact

SENTINEL = "SENTINEL-7f3a-user-wrote-this"
PACKAGES = Path(__file__).resolve().parents[1] / "packages"


@pytest.fixture(autouse=True)
def _content_off(monkeypatch):
    monkeypatch.delenv("ABI_LOG_USER_CONTENT", raising=False)


def test_redact_hides_content_but_keeps_a_fingerprint():
    out = redact(f"make me a game {SENTINEL}")
    assert SENTINEL not in out
    assert out.startswith("<text len=") and "sha=" in out
    assert redact(f"make me a game {SENTINEL}") == out          # same text, same fingerprint
    assert redact("another text") != out
    assert redact(None) == "<none>"
    assert SENTINEL not in redact({"query": SENTINEL})          # dicts too


def test_mask_email():
    assert mask_email("jane@example.com") == "j***@example.com"
    assert mask_email(None) == "<none>"
    assert mask_email("not-an-email") == "<redacted>"


def test_content_is_logged_only_when_asked(monkeypatch):
    monkeypatch.setenv("ABI_LOG_USER_CONTENT", "true")
    assert redact(SENTINEL) == SENTINEL
    assert mask_email("jane@example.com") == "jane@example.com"


class _Capture:
    """Lines abi_logging emits, straight from its logger: its stdout handler is
    created once and stays bound to whatever stdout existed then."""

    def __enter__(self):
        import logging
        from abi_core.common.utils import _setup_abi_logger
        self.lines, logger = [], _setup_abi_logger()
        self.handler = logging.Handler()
        self.handler.emit = lambda record: self.lines.append(record.getMessage())
        logger.addHandler(self.handler)
        self.logger = logger
        return self

    def __exit__(self, *a):
        self.logger.removeHandler(self.handler)

    @property
    def text(self):
        return "\n".join(self.lines)


def test_mcp_call_does_not_log_its_arguments_or_response():
    from abi_core.common import semantic_tools

    session = AsyncMock()
    session.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=f'{{"echo": "{SENTINEL}"}}')], isError=False)

    class _Session:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *a):
            return False

    with _Capture() as cap, patch.object(semantic_tools.client, "init_session", lambda *a, **k: _Session()):
        asyncio.run(semantic_tools.MCPToolkit().call("find_agent", query=f"build {SENTINEL}"))
    logged = cap.text
    assert "find_agent" in logged          # the line is there…
    assert SENTINEL not in logged          # …without the user's text


# ── Guard over the source ───────────────────────────────────────

# Names that hold what the user wrote, plans, prompts or model output.
USER_CONTENT = {
    "query", "prompt", "system_prompt", "SYSTEM_PROMPT", "kwargs", "text_content",
    "task_description", "email", "user_input", "rationale", "desc",
}
SAFE_CALLS = {"redact", "mask_email", "len", "sorted", "type"}
ROOTS = [PACKAGES / "abi-core/src/abi_core", PACKAGES / "abi-agents/src/abi_agents",
         PACKAGES / "abi-services/src/abi_services"]


def _unsafe_names(expr: ast.AST):
    """User-content names in `expr` that are not inside redact()/mask_email()/len()…"""
    if isinstance(expr, ast.Call) and getattr(expr.func, "id", None) in SAFE_CALLS:
        return set()
    found = set()
    if isinstance(expr, ast.Name) and expr.id in USER_CONTENT:
        found.add(expr.id)
    if isinstance(expr, ast.Attribute) and expr.attr in USER_CONTENT:
        found.add(expr.attr)
    for child in ast.iter_child_nodes(expr):
        found |= _unsafe_names(child)
    return found


def _leaks():
    leaks = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if "templates" in path.parts or "scaffolding" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "abi_logging" and node.args):
                    continue
                for part in ast.walk(node.args[0]):
                    if isinstance(part, ast.FormattedValue):
                        bad = _unsafe_names(part.value)
                        if bad:
                            leaks.append(f"{path.relative_to(PACKAGES)}:{node.lineno} {sorted(bad)}")
    return leaks


def test_no_log_line_interpolates_user_content():
    assert _leaks() == []
