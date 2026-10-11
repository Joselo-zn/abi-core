"""Measure the reviewer's one-call repair on the fixture sets.

Each set under tests/fixtures/repair_sets/ fails the integration review on
purpose (typical code-agent failures injected into sets that passed). For
each set and trial: one repair call with the current reviewer prompts
(REVIEWER_ROLE + build_repair_prompt), then the integration review again.

Not a unit test: it calls a real model and takes minutes. Run it before and
after changing the reviewer's prompts and compare.

    LLM_PROVIDER=gemini MODEL_NAME=gemini-3.6-flash LLM_API_KEY=... \
    TRIALS=2 python tests/measure/measure_repair.py

Spec: .abi/specs/implemented/reviewer-repair-rules-in-role.md
"""

import asyncio
import json
import os
import time
from pathlib import Path

from abi_core.agent.llm_provider import llm_config_from_env
from abi_core.common.integration_repair import repair_files
from abi_core.common.integration_review import review_files, static_findings
from abi_core.common.prompts.reviewer import REVIEWER_ROLE

SETS = Path(__file__).resolve().parents[1] / "fixtures" / "repair_sets"
TRIALS = int(os.getenv("TRIALS", "2"))


async def main():
    llm = llm_config_from_env()
    results = []
    for folder in sorted(p for p in SETS.iterdir() if p.is_dir()):
        files = {p.name: p.read_text() for p in sorted(folder.glob("*.py"))}
        report = await review_files(files)
        _, entry = static_findings(files)
        for trial in range(1, TRIALS + 1):
            t0 = time.time()
            changed = await repair_files(files, entry, report.as_text(), llm,
                                         system_prompt=REVIEWER_ROLE, changes_out={})
            after = await review_files({**files, **changed})
            row = {"set": folder.name, "trial": trial, "errors_before": len(report.errors),
                   "errors_after": len(after.errors), "passed": after.passed,
                   "secs": round(time.time() - t0)}
            print(json.dumps(row), flush=True)
            results.append(row)
    passed = sum(r["passed"] for r in results)
    print(f"passed {passed}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
