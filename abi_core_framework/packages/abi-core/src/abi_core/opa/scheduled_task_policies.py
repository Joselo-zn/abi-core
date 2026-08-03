"""
abi_core.opa.scheduled_task_policies — Default permissive `.rego` rule for
the `@agent.task_schedule` OPA gate (`abi/scheduled_task/allow`).

See .abi/tsd/2026-08-02-scheduled-task-opa-fail-open.md: since
`check_scheduled_task_policy` is already fail-open when OPA is unreachable,
publishing this default rule is NOT closing a "denied by default" bug (that
scenario doesn't happen) — it's operator discoverability: an explicit,
editable rule a project can find in its own `./opa` directory and tighten.

Mirrors `opa.core_policies.CorePolicyGenerator`'s "generate if missing" idiom,
but deliberately does NOT gate startup on success/failure the way that
generator does (its policies are mandatory; this one is opt-in and only
relevant to projects that both use `@agent.task_schedule` AND provisioned
OPA at all).
"""

from __future__ import annotations

from pathlib import Path

from abi_core.common.utils import abi_logging

DEFAULT_SCHEDULED_TASK_POLICY = """package abi.scheduled_task

# Default policy for @agent.task_schedule firings — permissive by default.
# check_scheduled_task_policy() already fails open when OPA is unreachable,
# so this rule exists for discoverability/auditability, not to avoid a
# deny-by-default gap. Tighten this rule to restrict which agents/tasks may
# fire, e.g.:
#
#   allow := false if input.task_name == "dangerous_job"

default allow := true
"""


def write_default_scheduled_task_policy(output_path: str) -> bool:
    """Write the default permissive rule to ``output_path`` if it doesn't
    already exist. Never overwrites a project's customized rule. Never
    raises — a write failure just logs a warning, since this is purely
    about discoverability, not correctness (the fail-open gate already
    behaves safely without this file).
    """
    try:
        output_file = Path(output_path)
        if output_file.exists():
            return False
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(DEFAULT_SCHEDULED_TASK_POLICY, encoding="utf-8")
        abi_logging(f"[⏰] Default scheduled_task OPA policy written: {output_path}")
        return True
    except Exception as e:  # noqa: BLE001 — never block agent startup on this
        abi_logging(f"[⚠️] Could not write default scheduled_task policy: {e}", level="warning")
        return False
