"""Zombie Agent — reviewer role (ZOMBIE_ROLE=reviewer).

Same pattern as the code agent: one entry task takes every request and runs
the steps for whoever is calling.

    "code_agent"                   a code agent hands in its work; when all the
                                   plan's agents arrived (or EXECUTION_TIMEOUT
                                   passed), the review starts in the background
    "orchestrator" (report)        wait for the review, answer with the report
    "orchestrator" + "errors"      the Orchestrator's verification failed:
                                   correct again (no new questions), report
    "orchestrator" + "confirmed"   nothing missing: leave

The review: read (plan, code, specs, docs, initial integration review in the
governed sandbox) → ask (≤ 5 questions per code agent, one round, then tell
every code agent it is done) → correct (one model call, writes the files of
agents that failed) → upload to review/repaired/.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.3-reviewer-agent.md
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from app import agent
from abi_core.agent.agent_response import AgentResponse
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent import lifecycle
from abi_agents.zombie.agent.config.config import config

MAX_QUESTIONS = 5   # per code agent (user decision, 2026-10-08)
CODE_TASK_TYPES = {"build_and_execute", "create_tools_and_execute"}

state: Dict[str, Any] = {
    "plan": None,
    "expected": {},      # task_id -> filename, from the plan
    "arrivals": {},      # task_id -> what the code agent sent
    "files": {},         # current version of every file of the set
    "specs": {},         # filename -> TDD
    "initial_review": None,
    "questions": {},     # filename -> [questions]
    "answers": {},       # filename -> answer text or "no answer"
    "changes": {},       # filename -> why (model's CHANGES)
    "repaired": {},      # filename -> project key in review/repaired/
    "failed": [],        # task ids whose agent failed or never arrived
    "missing": [],       # filenames that never arrived (the reviewer wrote them)
    "round": 0,
    "report": None,
    "communication_errors": [],  # A2A policy denials when calling code agents
}
_review: Optional[asyncio.Task] = None
_deadline: Optional[asyncio.Task] = None
_started_at = time.time()


def _parse(query: str) -> dict:
    try:
        data = json.loads(query) if isinstance(query, str) else query
    except (json.JSONDecodeError, TypeError):
        data = None
    return data if isinstance(data, dict) else {}


async def _load_plan() -> None:
    if state["plan"] is not None:
        return
    from abi_core.common import project_store

    plan = await project_store.load_json(config.RUN_ID, "plan", "plan.json")
    state["plan"] = plan
    state["expected"] = {
        t["task_id"]: (t.get("target") or {}).get("tag")
        for t in plan.get("tasks", [])
        if (t.get("target") or {}).get("tag") and t.get("type", "build_and_execute") in CODE_TASK_TYPES
    }
    abi_logging(f"[🔍] Reviewer for run {config.RUN_ID}: expecting {state['expected']}")


def _start_review(reason: str) -> None:
    global _review
    if _review is None:
        abi_logging(f"[🔍] Review starts: {reason}")
        _review = asyncio.create_task(_run_review())


def _ensure_deadline() -> None:
    """After EXECUTION_TIMEOUT from start-up, review with what arrived."""
    global _deadline
    if _deadline is not None:
        return

    async def _wait():
        await asyncio.sleep(max(0.0, _started_at + config.EXECUTION_TIMEOUT - time.time()))
        missing = sorted(set(state["expected"]) - set(state["arrivals"]))
        _start_review(f"deadline reached, missing {missing}")

    _deadline = asyncio.create_task(_wait())


async def _with_heartbeat(coro, context_id, task_id, msg):
    from abi_core.agent.agent import _HeartbeatDone

    async for item in agent._agent_instance._run_with_heartbeat(coro, context_id, task_id, msg):
        if isinstance(item, _HeartbeatDone):
            yield (item.value,)
        else:
            yield item


@agent.task(name="main", task_id="reviewer-main")
async def main(query, context_id=None, task_id=None):
    request = _parse(query)
    caller = request.get("caller", "orchestrator")
    await _load_plan()
    _ensure_deadline()

    if caller == "code_agent":
        tid = request.get("task_id")
        state["arrivals"][tid] = request
        waiting = sorted(set(state["expected"]) - set(state["arrivals"]))
        abi_logging(f"[🔍] Arrived {tid} ({request.get('status')}); waiting for {waiting or 'nobody'}")
        if not waiting:
            _start_review("all code agents arrived")
        yield AgentResponse.result({"received": tid, "waiting_for": waiting})
        return

    # The Orchestrator
    lifecycle.touch()
    if request.get("confirmed"):
        lifecycle.request_termination("Orchestrator confirmed nothing is missing")
        yield AgentResponse.result({"status": "terminating"})
        return

    if request.get("errors"):
        coro = _correct_again(str(request["errors"]))
        msg = "Reviewer: correcting the Orchestrator's findings..."
    else:
        _ensure_review_started_when_complete()
        coro = _await_review()
        msg = "Reviewer: reviewing the delivered files..."
    report = None
    async for item in _with_heartbeat(coro, context_id, task_id, msg):
        if isinstance(item, tuple):
            report = item[0]
        else:
            yield item
    lifecycle.start_watchdog(config.AGENT_NAME, config.EXECUTION_TIMEOUT)
    yield AgentResponse.result(report)


def _ensure_review_started_when_complete() -> None:
    if not set(state["expected"]) - set(state["arrivals"]):
        _start_review("all code agents arrived")


async def _await_review() -> dict:
    while _review is None:
        await asyncio.sleep(2)
    await asyncio.shield(_review)
    return state["report"]


async def _run_review() -> None:
    try:
        await agent.execute_step("review_read", run_id=config.RUN_ID)
        await agent.execute_step("review_ask")
        # Nothing verified wrong and nothing missing: no model call — every
        # change is a chance to break a file that works. The Orchestrator
        # still verifies.
        if state.get("initial_errors") or state["missing"]:
            await agent.execute_step("review_correct", report_text=state["initial_review"] or "")
        else:
            abi_logging("[🔍] Initial review clean and nothing missing — no correction")
            state["pending_upload"] = []
        await agent.execute_step("review_upload")
    except Exception as e:
        abi_logging(f"[❌] Review failed: {type(e).__name__}: {e}", level="error")
        state["report"] = _report(error=f"{type(e).__name__}: {e}")
    # If the Orchestrator never comes for the report (its run ended early),
    # leave after EXECUTION_TIMEOUT instead of staying forever.
    lifecycle.start_watchdog(config.AGENT_NAME, config.EXECUTION_TIMEOUT)


async def _correct_again(errors: str) -> dict:
    await agent.execute_step("review_correct", report_text=errors)
    await agent.execute_step("review_upload")
    return state["report"]


# ── Steps ───────────────────────────────────────────────────────

@agent.step(name="review_read")
@agent.sandboxed
async def review_read(run_id):
    """Download the set and run the initial integration review (sandbox
    through sandbox-service, tied to this run)."""
    from abi_core.common import project_store
    from abi_core.common.integration_review import review_files

    for area in ("code", "docs"):
        for name in await project_store.list_area(run_id, area):
            state["files"][name] = (await project_store.load(run_id, area, name)).decode("utf-8", errors="replace")
    for name in await project_store.list_area(run_id, "spec"):
        if name.endswith(".tdd.json"):
            state["specs"][name[: -len(".tdd.json")]] = await project_store.load_json(run_id, "spec", name)

    expected_files = {f for f in state["expected"].values() if f}
    state["missing"] = sorted(expected_files - set(state["files"]))
    state["failed"] = sorted(
        tid for tid in state["expected"]
        if tid not in state["arrivals"] or state["arrivals"][tid].get("status") != "completed"
    )
    report = await review_files(state["files"], run_sandbox=True)
    state["initial_review"] = report.as_text() if report else ""
    state["initial_errors"] = len(report.errors) if report else 0
    await project_store.save(run_id, "review", "integration-0.json", json.dumps({
        "text": state["initial_review"], "missing": state["missing"], "failed": state["failed"],
    }, ensure_ascii=False, indent=2).encode())
    abi_logging(f"[🔍] Read {sorted(state['files'])}; missing {state['missing']}; failed {state['failed']}")
    return {"files": sorted(state["files"]), "missing": state["missing"]}


@agent.step(name="review_ask")
async def review_ask():
    """One round of questions, then tell every code agent it is done."""
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.ephemeral_prompts import (
        REVIEWER_ROLE, build_reviewer_questions_prompt, parse_questions,
    )

    # filename (from the plan) -> what its code agent sent; only agents that
    # finished can answer about their file.
    agents = {state["expected"][tid]: a for tid, a in state["arrivals"].items()
              if tid in state["expected"] and a.get("status") == "completed" and a.get("agent")}
    if agents:
        prompt = build_reviewer_questions_prompt(sorted(agents), state["plan"], state["files"], state["specs"],
                                                 state["initial_review"], MAX_QUESTIONS)
        text = await invoke(config.LLM_CONFIG, prompt, system_prompt=REVIEWER_ROLE, call_timeout=120.0)
        state["questions"] = parse_questions(text, set(agents), MAX_QUESTIONS)

        async def ask(filename, questions):
            data = await _call_code_agent(agents[filename]["agent"], {"caller": "reviewer", "questions": questions})
            state["answers"][filename] = (data or {}).get("answers") or "no answer"

        await asyncio.gather(*(ask(f, q) for f, q in state["questions"].items()))
    # Every code agent that reached us is told it is done — a failed one
    # too, or it would wait for the reviewer until its own timeout.
    for a in state["arrivals"].values():
        if a.get("agent"):
            await _call_code_agent(a["agent"], {"caller": "reviewer", "done": True})
    abi_logging(f"[🔍] Questions {state['questions']}; answered {sorted(k for k, v in state['answers'].items() if v != 'no answer')}")
    return {"asked": sorted(state["questions"])}


@agent.step(name="review_correct")
async def review_correct(report_text):
    """Rewrite the set in one call (decision 02.3 a), with what only the
    reviewer has: specs, answers, missing files, the plan and its design."""
    from abi_core.common.ephemeral_prompts import REVIEWER_ROLE, plan_and_design_text, specs_text
    from abi_core.common.integration_repair import allowed_imports, repair_files
    from abi_core.common.integration_review import static_findings

    state["round"] += 1
    _, entry = static_findings(state["files"]) if state["files"] else ([], None)
    answers = "\n".join(f"- {f}: {a}" for f, a in sorted(state["answers"].items()))
    changes: Dict[str, str] = {}
    changed = await repair_files(
        state["files"], entry, report_text, _repair_llm_config(),
        allowed_imports=allowed_imports(state["plan"], list(state["files"]) + state["missing"]),
        system_prompt=REVIEWER_ROLE, answers=answers or None,
        missing=[m for m in state["missing"] if m not in state["files"]] or None,
        plan_and_design=plan_and_design_text(state["plan"]),
        specs=specs_text(state["specs"]) or None, changes_out=changes,
    )
    state["files"].update(changed)
    state["changes"].update({f: changes.get(f, "") for f in changed})
    state["pending_upload"] = sorted(changed)
    return {"changed": sorted(changed)}


@agent.step(name="review_upload")
async def review_upload():
    from abi_core.common import project_store

    for name in state.get("pending_upload", []):
        state["repaired"][name] = await project_store.save(
            config.RUN_ID, "review/repaired", name, state["files"][name].encode("utf-8"),
            metadata={"agent": config.AGENT_NAME, "round": str(state["round"])},
        )
    state["report"] = _report()
    await project_store.save_json(config.RUN_ID, "review", f"report-{state['round']}.json", state["report"])
    return {"uploaded": state.get("pending_upload", [])}


# ── Helpers ─────────────────────────────────────────────────────

def _repair_llm_config() -> dict:
    """The repair call's settings, as when the Orchestrator repaired: low
    temperature (the run that passed in one round used 0.2) and, on Ollama,
    a context window that fits every file plus the report and the answer —
    Ollama's default window would cut the prompt. Ollama only: some hosted
    models reject a non-default temperature."""
    import os

    llm = {**config.LLM_CONFIG}
    if str(llm.get("provider", "ollama")).lower() == "ollama":
        llm["temperature"] = float(os.getenv("INTEGRATION_REVIEWER_TEMPERATURE", "0.2"))
        llm["extra_params"] = {**(llm.get("extra_params") or {}),
                               "num_ctx": int(os.getenv("INTEGRATION_REVIEWER_NUM_CTX", "16384"))}
    return llm


def _report(error: Optional[str] = None) -> dict:
    """What the Orchestrator gets — built by code, no model call."""
    return {
        "caller": "reviewer",
        "run_id": config.RUN_ID,
        "round": state["round"],
        "status": "failed" if error else "repaired",
        "error": error,
        "repaired": dict(state["repaired"]),
        "changes": dict(state["changes"]),
        "questions": dict(state["questions"]),
        "answers": dict(state["answers"]),
        "failed_agents": list(state["failed"]),
        "missing_written": [m for m in state["missing"] if m in state["repaired"]],
        "initial_review": state["initial_review"],
        "communication_errors": list(state["communication_errors"]),
    }


async def _call_code_agent(agent_name: str, body: dict) -> Optional[dict]:
    """A2A call to a code agent by its card; None if it can't be reached
    (the review goes on without it)."""
    from uuid import uuid4

    from abi_core.common.a2a_response import A2AResponse
    from abi_core.common.abi_a2a import agent_connection
    from abi_core.common.agent_card_loader import build_agent_card
    from abi_core.common.semantic_tools import MCPToolkit

    try:
        found = await MCPToolkit().call("get_ephemeral_card", agent_name=agent_name)
        if not (isinstance(found, dict) and found.get("found")):
            abi_logging(f"[🔍] {agent_name} not found — going on without it", level="warning")
            return None
        payload = {"message": {"messageId": uuid4().hex, "role": "user",
                               "parts": [{"kind": "text", "text": json.dumps(body)}]}}
        chunks = []
        async for chunk in agent_connection(agent.agent_card, build_agent_card(found["agent_card"])[0], payload):
            chunks.append(chunk)
        for resp in reversed(A2AResponse.from_results(chunks)):
            if resp.data:
                return resp.data
        return {}
    except Exception as e:
        from a2a.utils.errors import InvalidParamsError
        from abi_core.common.abi_a2a import A2APolicyDenied
        if isinstance(e, (A2APolicyDenied, InvalidParamsError)):
            kind = "a2a_policy_denied" if isinstance(e, A2APolicyDenied) else "a2a_invalid_request"
            state["communication_errors"].append({"to": agent_name, "kind": kind, "detail": str(e)})
        abi_logging(f"[🔍] {agent_name} did not answer ({type(e).__name__}: {e}) — going on without it",
                    level="warning")
        return None
