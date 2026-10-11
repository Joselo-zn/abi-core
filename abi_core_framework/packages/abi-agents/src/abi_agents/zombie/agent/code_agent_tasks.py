"""Zombie Agent — Tasks.

One entry task receives every request (02.2). The request says who is
calling, and the task runs the steps for that:

    no "caller" / "orchestrator"   write the code (the plan's request)
    "reviewer" + "questions"       answer from what it did
    "reviewer" + "done"            leave

After writing the code, if the plan names a reviewer, ``send_link`` hands it
the work in the background and the agent stays alive for its questions.
Without a reviewer (a plan with no code review, an older Orchestrator) the
agent ends after answering, as before.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.2-code-agent-lifecycle.md
"""

import asyncio
import json
import time

from app import agent
from abi_core.agent.agent_response import AgentResponse
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent import lifecycle
from abi_agents.zombie.agent.config.config import config


def _parse(query: str) -> dict:
    try:
        data = json.loads(query) if isinstance(query, str) else query
    except (json.JSONDecodeError, TypeError):
        data = None
    return data if isinstance(data, dict) else {"query": query}


async def _with_heartbeat(coro, context_id, task_id, status_msg):
    """Run a step while the caller keeps getting heartbeats (UI, and the
    caller's inactivity timeout). Yields AgentResponses, then the result
    wrapped in a one-item tuple."""
    from abi_core.agent.agent import _HeartbeatDone

    async for item in agent._agent_instance._run_with_heartbeat(coro, context_id, task_id, status_msg):
        if isinstance(item, _HeartbeatDone):
            yield (item.value,)
        else:
            yield item


@agent.task(name="main", task_id="code-agent-main")
async def main(query, context_id=None, task_id=None):
    request = _parse(query)
    caller = request.get("caller", "orchestrator")

    if caller == "reviewer":
        lifecycle.touch()
        if request.get("done"):
            yield AgentResponse.result(await agent.execute_step("self_destruct", reason="reviewer done"))
            return
        result = None
        async for item in _with_heartbeat(
            agent.execute_step("answer_questions", questions=request.get("questions") or []),
            context_id, task_id, "Answering the reviewer...",
        ):
            if isinstance(item, tuple):
                result = item[0]
            else:
                yield item
        yield AgentResponse.result(result)
        return

    # The plan's request: write the code (the same steps the DAG ran).
    text = request.get("query", query)
    outputs = {}
    try:
        for step, kwargs, msg in (
            ("gather_context", lambda: {"query": text}, "Loading context..."),
            ("analyze_and_execute", lambda: {"context": outputs["gather_context"], "query": text},
             "Executing pipeline..."),
            ("synthesize_and_report", lambda: {"execution_result": outputs["analyze_and_execute"],
                                               "context": outputs["gather_context"]}, "Uploading results..."),
        ):
            async for item in _with_heartbeat(agent.execute_step(step, **kwargs()), context_id, task_id, msg):
                if isinstance(item, tuple):
                    outputs[step] = item[0]
                else:
                    yield item
    except Exception as e:
        lifecycle.work_record.update({"status": "failed", "error": f"{type(e).__name__}: {e}"})
        abi_logging(f"[❌] Code agent failed: {e}", level="error")
        await _hand_off_or_end(outputs)
        yield AgentResponse.error(str(e) or type(e).__name__)
        return

    await _hand_off_or_end(outputs)
    yield AgentResponse.result(outputs["synthesize_and_report"])


async def _hand_off_or_end(outputs: dict) -> None:
    """With a reviewer in the plan: send it the work in the background and
    stay. Without one, or for the old integration reviewer: end after this
    response, as before."""
    from abi_core.common.integration_review import REVIEW_TASK_PREFIX

    process_context = (outputs.get("gather_context") or {}).get("process_context") or {}
    reviewer = process_context.get("reviewer")
    run_id = process_context.get("run_id")
    if not reviewer or not run_id or (config.CONTEXT_ID or "").startswith(REVIEW_TASK_PREFIX):
        lifecycle.request_termination("no reviewer in this plan")
        return
    await agent.execute_task_async(
        "send_link", reviewer=reviewer, run_id=run_id,
        report=_report(run_id, outputs.get("synthesize_and_report") or {}),
    )


def _report(run_id: str, synthesis: dict) -> dict:
    from abi_core.common import project_store

    files = {"code": [], "spec": [], "docs": []}
    for name in lifecycle.work_record.get("files_written") or []:
        area = project_store.area_for(name)
        files[area].append(project_store.project_key(run_id, area, name))
        if area == "code":
            files["spec"].append(project_store.project_key(run_id, "spec", f"{name}.tdd.json"))
    return {
        "caller": "code_agent",
        "agent": config.AGENT_NAME,
        "task_id": config.CONTEXT_ID,
        "status": lifecycle.work_record.get("status") or synthesis.get("status", "failed"),
        "error": lifecycle.work_record.get("error"),
        "files": files,
    }


@agent.task_async(name="send_link", max_retries=1)
async def send_link(reviewer, run_id, report):
    """Find the run's reviewer in the semantic layer (exact name) and hand
    it the work over A2A. Connection failures are retried until
    EXECUTION_TIMEOUT; a denial by the A2A policy stops at the first attempt
    (asking again gets the same answer) and is recorded in the run's folder,
    where the Orchestrator reports it to the user. Either way the run goes
    on: the reviewer completes what it has at its deadline. If the hand-off
    doesn't succeed the agent ends — live 2026-10-09 a single failed attempt
    left five code agents alive for 18 hours."""
    try:
        outcome, detail = await _hand_off(reviewer, report, deadline=time.time() + config.EXECUTION_TIMEOUT)
    except Exception as e:  # noqa: BLE001 — whatever happened, the agent must not stay behind
        abi_logging(f"[🔗] Hand-off crashed ({type(e).__name__}: {e})", level="error")
        outcome, detail = "error", f"{type(e).__name__}: {e}"
    if outcome == "sent":
        lifecycle.start_watchdog(config.AGENT_NAME, config.EXECUTION_TIMEOUT)
        return {"sent": True}
    if outcome in ("policy", "invalid"):
        await _record_handoff_error(run_id, reviewer, detail,
                                    "a2a_policy_denied" if outcome == "policy" else "a2a_invalid_request")
    await lifecycle.terminate_now(config.AGENT_NAME, f"could not hand the work to '{reviewer}': {detail}")
    return {"sent": False, "outcome": outcome}


async def _record_handoff_error(run_id: str, reviewer: str, detail: str, kind: str) -> None:
    """One file per code agent (the object store has no append), read by the
    Orchestrator for the final answer."""
    from abi_core.common import project_store

    try:
        await project_store.save_json(run_id, "review", f"handoff-{config.CONTEXT_ID}.json", {
            "task_id": config.CONTEXT_ID, "agent": config.AGENT_NAME, "reviewer": reviewer,
            "kind": kind, "detail": detail,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    except Exception as e:  # noqa: BLE001 — the report is best effort; ending the agent is not
        abi_logging(f"[🔗] Could not record the hand-off error: {e}", level="warning")


async def _hand_off(reviewer: str, report: dict, deadline: float, pause: float = 15.0):
    """Look the reviewer up and send the report. Returns (outcome, detail):
    "sent"; "policy" — the A2A policy denied it; "invalid" — the reviewer
    rejected the request as malformed (InvalidParamsError) — both at the
    first attempt, since asking again gets the same answer (user decision
    2026-10-10); "timeout" — connection failures until the deadline."""
    from uuid import uuid4

    from a2a.utils.errors import InvalidParamsError
    from abi_core.common.abi_a2a import A2APolicyDenied, agent_connection
    from abi_core.common.agent_card_loader import build_agent_card
    from abi_core.common.semantic_tools import MCPToolkit

    attempt = 0
    last = "reviewer not found"
    while time.time() < deadline:
        attempt += 1
        try:
            found = await MCPToolkit().call("get_ephemeral_card", agent_name=reviewer)
            if isinstance(found, dict) and found.get("found"):
                payload = {"message": {"messageId": uuid4().hex, "role": "user",
                                       "parts": [{"kind": "text", "text": json.dumps(report)}]}}
                async for _ in agent_connection(agent.agent_card, build_agent_card(found["agent_card"])[0], payload):
                    pass
                abi_logging(f"[🔗] Work handed to {reviewer} (attempt {attempt}): {report['files']}")
                return "sent", ""
            abi_logging(f"[🔗] Reviewer '{reviewer}' not registered yet (attempt {attempt})")
        except A2APolicyDenied as e:
            abi_logging(f"[🔗] Hand-off denied by the A2A policy — not retrying: {e}", level="error")
            return "policy", str(e)
        except InvalidParamsError as e:
            abi_logging(f"[🔗] Hand-off rejected as an invalid request — not retrying: {e}", level="error")
            return "invalid", f"InvalidParamsError: {e}"
        except Exception as e:  # noqa: BLE001 — connection failures are retried until the deadline
            last = f"{type(e).__name__}: {e}"
            abi_logging(f"[🔗] Hand-off attempt {attempt} failed ({last}); retrying", level="warning")
        await asyncio.sleep(pause)
    return "timeout", last
