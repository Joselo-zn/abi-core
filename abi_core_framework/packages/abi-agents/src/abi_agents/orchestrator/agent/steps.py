"""Orchestrator Agent — Steps.

DAG (deterministic, runs before the LLM gets any freedom — see
.abi/tsd/2026-08-2X-orchestrator-tool-call-routing.md):
  classify_query | guardian_validate  (parallel)
    -> gate_decision

`classify_query` only does sentinel matching (button clicks) and peeks at
pending clarification/plan state — no LLM call. Everything that used to be
`call_planner` -> `extract_plan` -> `check_model_availability` (tools.py) is
no longer part of the DAG: the decision to call the Planner now comes from
the Orchestrator's reasoning turn (a tool call, not a DAG classification),
which doesn't exist yet when this DAG runs — same reason `build_workflow`
was never a DAG node. They're plain functions now, called directly by
`orchestrator.py::_call_planner_and_respond`.
"""

import asyncio
import json

from app import agent
from abi_core.common.utils import abi_logging, format_plan_summary, format_conversation_summary, plan_execution_order
from abi_core.common.a2a_response import A2AResponse
from abi_core.common.semantic_tools import tool_find_agent, MCPToolkit
from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode
from a2a.types import AgentCard
from abi_core.common.agent_card_loader import build_agent_card, get_agent_url
from abi_core.agent.agent import AbiAgent
from config import AGENT_CARD, config

# Agents that must NEVER be deregistered (infrastructure)
INFRA_AGENTS = {"builder", "planner", "orchestrator", "guardian", "semantic-layer"}

# Background tasks (ephemeral cleanup, see _spawn_background) must be kept
# referenced or asyncio may garbage-collect them mid-flight.
_background_tasks: set = set()


def _spawn_background(coro) -> None:
    """Fire-and-forget a coroutine for housekeeping that must never block the
    caller's critical path (see Paso 3/4 of
    .abi/specs/infra-agent-lookup-ephemeral-collision.md)."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _is_referenced_by_plan(name: str, plan_tasks: list) -> bool:
    """Paso 2: 'trabajando' = referenced by a task_id in the plan/session
    currently in flight — NOT liveness (a legitimate ephemeral can take
    minutes and still be genuinely working). No plan_tasks means there's no
    plan yet at this call site, so nothing can legitimately reference the
    agent — vacuously orphaned."""
    for t in (plan_tasks or []):
        for a in t.get("agents", []):
            a_name = a.get("name") if isinstance(a, dict) else getattr(a, "name", None)
            if a_name == name:
                return True
    return False


async def _cleanup_orphaned_ephemeral(name: str, role: str, plan_tasks: list = None) -> None:
    """Paso 3 + 4: housekeeping only — runs in the background, never on the
    request's critical path (that's guaranteed by the blacklist added before
    this is spawned, not by this finishing). Unregisters the stale card,
    destroys the stuck container, then sweeps for siblings from the same
    batch via recommend_agents."""
    from abi_core.common.container_runtime import destroy_container

    toolkit = MCPToolkit()

    async def _destroy(agent_name: str) -> None:
        try:
            await toolkit.call("unregister_agent", agent_name=agent_name)
            await destroy_container(agent_name)
            abi_logging(f"[🧹] Cleaned up orphaned ephemeral: {agent_name}")
        except Exception as e:
            abi_logging(f"[⚠️] Cleanup of '{agent_name}' failed (non-critical): {e}")

    await _destroy(name)

    try:
        candidates = await toolkit.call(
            "recommend_agents", task_description=f"abi agent {role}", max_agents=5
        )
        for c in (candidates or []):
            candidate_card = c.get("agent", {}) if isinstance(c, dict) else {}
            c_name = candidate_card.get("name", "")
            if not c_name or not c_name.lower().startswith("ephemeral") or c_name == name:
                continue
            if _is_referenced_by_plan(c_name, plan_tasks):
                continue
            await toolkit.call("blacklist_agent", agent_id=f"agent://{c_name}")
            await _destroy(c_name)
    except Exception as e:
        abi_logging(f"[⚠️] Ephemeral sweep for '{role}' failed (non-critical): {e}")


async def find_infra_agent(role: str, plan_tasks: list = None):
    """Resolve a reserved infra agent (guardian/planner/builder) by name, with
    a safety net against ephemeral/zombie collisions. See
    .abi/specs/infra-agent-lookup-ephemeral-collision.md

    Primary mechanism: exact, non-semantic lookup by filename stem
    (`get_agent_card_by_stem`) — the 4 reserved infra agents are known, fixed
    singletons on disk, never dynamically-registered ephemeral cards, so this
    is structurally immune to the ephemeral-collision problem, not just
    resistant to it. Live-verified need for this (not just theoretical):
    even with ephemeral cards excluded, vector-similarity ranking between a
    handful of short, topically-similar role descriptions is unstable — "abi
    agent planner" ranked the Orchestrator's own card above the Planner's,
    margin under 0.01, well within noise. A known singleton needs a
    deterministic lookup, not a best-effort one.
    """
    # No try/except originally guarded this call — a live incident
    # (2026-09-21: "planner" resolved to a stuck ephemeral even with this
    # exact-match path in place) could not be root-caused afterward because
    # a silent fall-through here leaves zero trace of *why* it fell through.
    # Logging every non-primary outcome explicitly so this is never a
    # multi-hour mystery again.
    try:
        exact = await MCPToolkit().call("get_agent_card_by_stem", stem=f"{role}_agent")
    except Exception as e:
        abi_logging(f"[⚠️] find_infra_agent('{role}'): get_agent_card_by_stem raised {type(e).__name__}: {e} — falling back to vector search")
        exact = None

    if isinstance(exact, dict) and exact and not exact.get("error"):
        card, _meta = build_agent_card(exact)
        return card

    abi_logging(f"[⚠️] find_infra_agent('{role}'): exact-match lookup did not return a usable card ({exact!r}) — falling back to vector search")

    # Fallback below only runs if the static card file is missing/renamed —
    # kept as defense in depth, still protected by exclude_ephemeral + the
    # safety net that follows (same protections as before this function had
    # an exact-match primary path).
    query = f"abi agent {role}"
    card = await tool_find_agent.ainvoke({"query": query, "exclude_ephemeral": True})
    abi_logging(f"[⚠️] find_infra_agent('{role}'): vector-search fallback returned {getattr(card, 'name', card)!r}")

    # a2a.types.AgentCard is a strict schema — build_agent_card() doesn't
    # preserve a custom `ephemeral` field, so detect via the naming
    # convention every ephemeral/zombie container is built with
    # (builder/agent/steps.py: f"ephemeral-{task_id}-{timestamp}"), which
    # DOES survive as the card's `name`.
    name = getattr(card, "name", "") or ""
    if not card or not name.lower().startswith("ephemeral"):
        return card

    abi_logging(f"[🧟] '{role}' lookup returned an ephemeral card ({name}) — safety net triggered")

    if _is_referenced_by_plan(name, plan_tasks):
        abi_logging(f"[🧟] '{name}' is referenced by a task in the current plan — leaving it alone")
        return card

    # Paso 2.5: immediate, local blacklist in the semantic layer — makes the
    # retry below safe without waiting on the background cleanup.
    await MCPToolkit().call("blacklist_agent", agent_id=f"agent://{name}")

    _spawn_background(_cleanup_orphaned_ephemeral(name, role, plan_tasks))

    return await tool_find_agent.ainvoke({"query": query, "exclude_ephemeral": True})

# Working-memory topic used to mark a session awaiting a planner clarification
PENDING_CLARIFICATION_TOPIC = "pending_clarification"

# Sentinel the ClarificationForm custom element sends (chainlit_app.py) —
# same "deterministic, zero-LLM" pattern as PLAN_CONFIRM_APPROVE/REJECT/MODIFY
# below, applied to clarification answers. See
# .abi/specs/deterministic-clarification-answers.md.
CLARIFICATION_ANSWER_SENTINEL = "__clarification_answer__"

# Sentinels: framework-level since 2026-08-03, see abi_core.agent.plan_confirmation
# (extracted so a standalone agent can use the same confirm/reject/modify state
# machine, not just the swarm). classify_plan_confirmation_sentinel is the sync,
# zero-LLM sentinel-only slice of it (2026-08 tool-call routing redesign) —
# free-text interpretation of a pending plan is now the reasoning turn's job
# (resolve_pending_plan action, see build_routing_contract below and
# abi_core.agent.routing_tools), not this DAG's.
from abi_core.agent.plan_confirmation import (
    PLAN_CONFIRM_APPROVE,
    PLAN_CONFIRM_REJECT,
    PLAN_CONFIRM_MODIFY,
    classify_plan_confirmation_sentinel,
)


@agent.step(
    name="classify_query",
    input_map={
        "query": "$input.query",
        "context_id": "$input.context_id",
        "session_context": "$input.session_context",
    },
)
async def classify_query(query, context_id="", session_context=None):
    """Sentinel check + pending-clarification peek. No LLM call — everything
    that needs to interpret free text (is this a confirmation reply? does it
    answer the pending clarification? is it a new complex request?) is the
    reasoning turn's job now (orchestrator.py::_reasoning_turn), not this
    step's. `session_context` is passed in via $input because this function
    has no `self`/session_backend access — orchestrator.py reads/writes it.
    """
    session_context = session_context or {}

    # ── Deterministic check: is this a plan-confirmation button click? ──
    sentinel_result = classify_plan_confirmation_sentinel(query, session_context)
    if sentinel_result is not None:
        abi_logging(f"[🔁] Plan confirmation sentinel: {sentinel_result['classification']} for session '{context_id}'")
        if sentinel_result["classification"] == "plan_modify_feedback":
            # Modify-with-feedback in one step (PlanReview card) — same
            # gate path as a reply to "¿qué querés cambiar?" below.
            return {"classification": "plan_modification_feedback", "feedback": sentinel_result["feedback"]}
        return sentinel_result

    # ── Deterministic check: free-text reply to "¿qué querés cambiar?" ──
    # Mirrors clarification_answered below — awaiting_plan_modification is
    # set by code (orchestrator.py, action=plan_modify_requested) right
    # before asking this question, so ANY reply that follows is
    # unambiguously the modification feedback, never a new unrelated
    # request. Used to fall through to reasoning_required, where the
    # model could (and did, reproduced live 2026-09-29) pick the dead-end
    # answer_directly action instead of resolve_pending_plan — the turn
    # ended in prose ("vamos a crear un plan...") with no plan ever
    # created. See .abi/specs/orchestrator-unified-routing-contract.md.
    if session_context.get("awaiting_plan_modification"):
        abi_logging(f"[🔁] Plan modification feedback received for session '{context_id}'")
        return {"classification": "plan_modification_feedback", "feedback": query}

    # ── Peek (never clear here) at a pending clarification, if any ──
    pending_clarification = await _peek_pending_clarification(context_id)

    # ── Deterministic check: is this the clarification form's submit? ──
    # Same reasoning as the plan-confirmation sentinel above — the form
    # (chainlit_app.py's ClarificationForm custom element) sends a JSON
    # payload instead of free text specifically so this never has to be an
    # LLM guess. Root cause this replaces: the reasoning turn's
    # `resolve_pending_clarification` decision used the *default* model
    # (never the profiled-better one — see
    # .abi/tsd/2026-09-09-routing-decision-model-profiling.md, which only
    # covered `resolve_pending_plan`), and a misclassified short reply
    # discarded the real `original_query`, replacing it with just the
    # fragment — reproduced live, see
    # .abi/specs/deterministic-clarification-answers.md. Only trusted when
    # a clarification is genuinely pending — a form submitted for a stale
    # session with no pending clarification falls through to
    # reasoning_required like any other message, same "orphaned" safety net
    # already in place for plan-confirmation sentinels.
    if pending_clarification:
        try:
            parsed = json.loads(query)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed.get("_sentinel") == CLARIFICATION_ANSWER_SENTINEL:
            abi_logging(f"[🔁] Clarification form submitted for session '{context_id}'")
            return {
                "classification": "clarification_answered",
                "answers": parsed.get("answers", {}),
                "pending_clarification": pending_clarification,
            }

    return {"classification": "reasoning_required", "pending_clarification": pending_clarification or None}


async def _peek_pending_clarification(context_id: str) -> dict:
    """Return the pending-clarification event for a session, or {} if none.
    Read-only — unlike the pre-redesign `_load_pending_clarification`, this
    does NOT clear it. Clearing now only happens when the reasoning turn's
    `resolve_pending_clarification` tool is actually called (orchestrator.py)
    — never just because a message arrived while one was pending, which was
    the root cause of the "no hablo ingles" bug this redesign fixes.
    """
    if not config.AGENT_MEMORY_URL or not context_id:
        return {}

    try:
        from abi_core.memory import get_short_term_memory

        raw = await get_short_term_memory(
            context_id=context_id, memory_url=config.AGENT_MEMORY_URL
        )
        if not raw:
            return {}

        # Working memory accumulates; a clarification is ACTIVE only if the most
        # recent clarification-related marker is a 'pending' one (not 'resolved').
        last_pending = None
        for line in raw.splitlines():
            if "clarification_resolved" in line:
                last_pending = None  # a later resolution cancels an earlier pending
            elif PENDING_CLARIFICATION_TOPIC in line:
                last_pending = line
        if not last_pending:
            return {}

        return _extract_clarification_payload(last_pending)
    except Exception as e:
        abi_logging(f"[⚠️] Could not read pending clarification: {e}")
        return {}


def _extract_clarification_payload(text: str) -> dict:
    """Extract the JSON payload embedded in a pending_clarification memory line."""
    import json
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return {}


async def _clear_pending_clarification(context_id: str) -> None:
    """Mark the pending clarification as resolved in short-term memory."""
    try:
        from abi_core.memory import add_short_term_memory

        await add_short_term_memory(
            topic="clarification_resolved",
            task=context_id,
            content="clarification_resolved marker",
            context_id=context_id,
            memory_url=config.AGENT_MEMORY_URL,
        )
    except Exception as e:
        abi_logging(f"[⚠️] Could not clear pending clarification: {e}")


@agent.step(
    name="guardian_validate",
    input_map={
        "query": "$input.query",
        "context_id": "$input.context_id",
    },
)
async def guardian_validate(query, context_id):
    """Call Guardian agent to validate query security.

    Checks: prompt injection, reverse engineering, policy compliance.
    Returns dict with 'allowed', 'reason', and 'status'.
    """
    try:
        guardian_card = await find_infra_agent("guardian")
        if not guardian_card:
            abi_logging("[⚠️] Guardian agent not found — cannot validate")
            return {
                "status": "error",
                "allowed": False,
                "reason": "Guardian service unavailable",
            }

        # Call guardian via A2A
        validation_query = json.dumps({
            "action": "validate_query",
            "query": query,
            "context_id": context_id,
            "checks": ["prompt_injection", "reverse_engineering", "policy_compliance"],
        })

        workflow = AgentInteractionFlow()
        node = InteractionFlowNode(
            task=validation_query,
            source_agent_card=AGENT_CARD,
            target_agent_card=guardian_card,
            node_key="guardian_gate",
            node_label="Security Validation",
        )
        workflow.add_node(node)
        workflow.set_node_attributes(
            node.id, {"context_id": context_id, "query": validation_query}
        )
        workflow.set_source_card(AGENT_CARD)

        results = []
        async for chunk in workflow.run_workflow():
            results.append(chunk)

        # Parse guardian response
        for resp in A2AResponse.from_results(results):
            if resp.data:
                allowed = resp.data.get("allowed", True)
                return {
                    "status": "blocked" if not allowed else "approved",
                    "allowed": allowed,
                    "reason": resp.data.get("reason", ""),
                    "risk_score": resp.data.get("risk_score", 0.0),
                }
            if resp.text:
                # Guardian responded with text — assume approved
                abi_logging(f"[🛡️] Guardian text response: {resp.text[:100]}")
                return {"status": "approved", "allowed": True, "reason": resp.text}

        # No parseable response — treat as approved with warning
        abi_logging("[⚠️] Guardian returned no parseable response, defaulting to approved")
        return {"status": "approved", "allowed": True, "reason": "No guardian response parsed"}

    except Exception as e:
        abi_logging(f"[❌] Guardian validation failed: {e}")
        return {
            "status": "error",
            "allowed": False,
            "reason": f"Guardian error: {str(e)}",
        }


# ── Level 1: Gate decision (depends on both level 0 nodes) ──────

@agent.step(
    name="gate_decision",
    depends_on=["classify_query", "guardian_validate"],
    input_map={
        "triage": "$classify_query",
        "guardian": "$guardian_validate",
        "query": "$input.query",
    },
)
def gate_decision(triage, guardian, query):
    """Merge triage + guardian results and decide how to proceed."""
    guardian_status = guardian.get("status", "error")

    # Guardian failed (timeout, unreachable, etc.)
    if guardian_status == "error":
        abi_logging(f"[❌] Guardian failed: {guardian.get('reason', 'unknown')}")
        return {
            "action": "system_error",
            "message": "El sistema experimentó una falla en la validación de seguridad. Por favor reintente más tarde.",
            "guardian_reason": guardian.get("reason", ""),
        }

    # Guardian blocked (injection, reverse engineering, policy violation)
    if guardian_status == "blocked":
        abi_logging(f"[🛡️] Query blocked by guardian: {guardian.get('reason', '')}")
        return {
            "action": "blocked",
            "message": "Tu solicitud no puede ser procesada por razones de seguridad.",
            "guardian_reason": guardian.get("reason", ""),
        }

    # Guardian approved — proceed based on triage
    classification = triage.get("classification", "complex")

    # Plan confirmation replies via sentinel (button click) — deterministic,
    # no planner/builder involved, no LLM. Free-text replies to a pending
    # plan/clarification no longer classify here at all — that's the
    # reasoning turn's job (orchestrator.py::_reasoning_turn), see below.
    if classification == "plan_confirmed":
        abi_logging("[✅] Gate: plan confirmed by user")
        return {"action": "execute_confirmed_plan", "plan": triage.get("pending_plan")}

    if classification == "plan_rejected":
        abi_logging("[❌] Gate: plan rejected by user")
        return {"action": "plan_rejected"}

    if classification == "plan_modify_requested":
        abi_logging("[✏️] Gate: user wants to modify the plan")
        return {"action": "plan_modify_requested"}

    if classification == "clarification_answered":
        abi_logging("[✅] Gate: clarification form answered by user")
        return {
            "action": "clarification_answered",
            "answers": triage.get("answers", {}),
            "pending_clarification": triage.get("pending_clarification"),
        }

    if classification == "plan_modification_feedback":
        abi_logging("[🔁] Gate: plan modification feedback received")
        return {"action": "plan_modification_feedback", "feedback": triage.get("feedback", query)}

    if classification == "plan_confirmation_orphaned":
        # query looked like an approve/reject/modify reply, but there's no
        # pending plan in this session to apply it to — most likely lost
        # session continuity (no token, so each request lands in a fresh
        # anonymous context). Say so instead of silently planning around the
        # literal word "aprobado"/"sí"/etc.
        abi_logging("[⚠️] Gate: plan-confirmation-looking reply with no pending plan", level="warning")
        return {"action": "plan_confirmation_orphaned"}

    # classification == "reasoning_required" — everything else (new request,
    # clarification reply, or free text about a pending plan) goes to the
    # LLM's own reasoning turn with tools, instead of being pre-classified
    # here by code.
    abi_logging("[🧠] Gate: handing off to the reasoning turn")
    return {"action": "reasoning_turn", "pending_clarification": triage.get("pending_clarification")}


# ── Routing contract — plain function, NOT a DAG node ────────────
#
# Only needed when gate_decision produced action="reasoning_turn" — every
# other action (execute_confirmed_plan, blocked, system_error, ...) skips it
# entirely, same reasoning as why call_planner/build_workflow below aren't
# DAG nodes either. Called directly by orchestrator.py::stream(). See
# .abi/specs/orchestrator-unified-routing-contract.md.

def build_routing_contract(query: str, session_ctx: dict, pending_clarification: dict) -> dict:
    """Deterministically assemble the one contract shape the reasoning
    turn's structured decision is built against — same shape regardless of
    whether a plan/clarification is pending or nothing is. `valid_actions`
    is computed here, once, instead of being recomputed (and able to
    diverge) in the LLM-facing prompt-building code.
    """
    pending_plan = session_ctx.get("pending_plan")

    if pending_plan:
        # No `answer_directly` escape here — deliberately. Reproduced live
        # 2026-09-30: with a plan pending, 7 of 7 free-text replies
        # ("comienza", "listo", "ya crea el maldito juego", ...) picked
        # answer_directly and produced chatty acknowledgment text instead
        # of ever resolving the plan — not a ~60% classification error,
        # every single one dodged. Any free text while a plan is pending
        # is *always* about that plan (approve/reject/modify) — there is
        # no legitimate "just chat" case here, so the schema shouldn't
        # offer one. Forces resolve_pending_plan's own approve/reject/
        # modify sub-decision instead of a decision on whether to decide.
        valid_actions = ["resolve_pending_plan"]
    elif pending_clarification:
        valid_actions = ["resolve_pending_clarification", "answer_directly"]
    else:
        valid_actions = ["create_plan", "answer_directly"]

    return {
        "query": query,
        "recent_conversation_summary": format_conversation_summary(session_ctx.get("conversation_summary")),
        "pending_plan_summary": format_plan_summary(pending_plan) if pending_plan else None,
        "pending_clarification_question": pending_clarification.get("clarification"),
        "valid_actions": valid_actions,
        # Consumed by the caller right after this call (see orchestrator.py's
        # stream()) — shows up exactly once, on the turn right after the
        # failure, never again. See .abi/specs/orchestrator-last-error-awareness.md.
        "recent_error_summary": session_ctx.get("last_error"),
    }


async def call_planner(query, context_id, task_id):
    """Call Planner agent and return raw A2A results."""
    abi_logging(f"[📞] Calling Planner: {query}")

    planner_card = await find_infra_agent("planner")
    if not planner_card:
        raise ValueError("Could not find Planner agent")

    workflow = AgentInteractionFlow()
    node = InteractionFlowNode(
        task=query,
        source_agent_card=AGENT_CARD,
        target_agent_card=planner_card,
        node_key="planner",
        node_label="Planning Phase",
    )
    workflow.add_node(node)
    workflow.set_node_attributes(
        node.id, {"context_id": context_id, "task_id": task_id, "query": query}
    )
    workflow.set_source_card(AGENT_CARD)

    results = []
    async for chunk in workflow.run_workflow():
        results.append(chunk)
    return results


def extract_plan(planner_results):
    """Extract execution plan from Planner results using A2AResponse."""
    abi_logging(f"[🔍] extract_plan received {len(planner_results)} results")
    for i, r in enumerate(planner_results):
        parsed = A2AResponse.parse(r)
        abi_logging(f"  [{i}] {parsed}")

    needs_clarification, msg, questions = A2AResponse.find_clarification(planner_results)
    if needs_clarification:
        return {"clarification": msg, "questions": questions}

    plan = A2AResponse.find_plan(planner_results)
    if not plan:
        return {"error": "Could not generate execution plan"}

    abi_logging(f"[📋] Plan received with {len(plan.get('tasks', []))} tasks")
    return {"plan": plan}


def _topological_order(tasks: list) -> list:
    """Execution order of a plan's tasks — now framework-owned
    (abi_core.common.utils.plan_execution_order) so the plan review card
    numbers tasks exactly as they run."""
    return plan_execution_order(tasks)


async def build_workflow(plan_result, context_id, task_id):
    """Build AgentInteractionFlow from the extracted plan.

    NOT a DAG step — this function calls the Builder for real
    (build_flow.run_workflow() below actually creates Docker containers for
    build_and_execute/create_tools_and_execute tasks), so it must only run
    *after* the user has approved the plan. orchestrator.py::stream() calls
    it directly once a plan is confirmed. Same reasoning as call_planner/
    extract_plan/check_model_availability (tools.py) — none of these are DAG
    nodes anymore since the 2026-08 tool-call routing redesign.

    Handles three task types:
    - "execute": agent exists → add directly to workflow
    - "build_and_execute": no agent, tools exist → call builder first
    - "create_tools_and_execute": no agent, no tools → call builder first
    """
    # Gate passthrough or errors — pass through
    if "gate_passthrough" in plan_result or "clarification" in plan_result or "error" in plan_result:
        return plan_result

    plan = plan_result["plan"]
    methodology = plan.get("methodology")
    rationale = plan.get("methodology_rationale", "")
    # Local context: prepended to what each executing agent receives so it
    # knows which decomposition methodology this plan follows — regardless
    # of whether it's an existing agent ("execute") or an ephemeral one
    # ("build_and_execute"/"create_tools_and_execute"). System-wide (global)
    # visibility is handled separately by orchestrator.py, which persists the
    # methodology to short-term memory when the plan is first confirmed.
    from abi_core.common.prompts.orchestrator import build_methodology_note
    methodology_block = build_methodology_note(methodology, rationale)
    workflow = AgentInteractionFlow()
    nodes = {}
    # Dependencies first: a task's artifact keys are built from its
    # dependencies' already-assigned agents (nodes[dep_id].target_agent_card
    # below). In plan order, an entry point listed BEFORE its modules found
    # none of them assigned yet and silently got artifacts=[] — reproduced
    # live 2026-10-03: main.py (task_1, depending on task_2..task_5) started
    # with an empty workspace and invented module names that didn't exist.
    # Latent until the Planner's technical-design phase started putting the
    # entry point first with real dependencies. See
    # .abi/fixes/2026-10-03-cross-file-integration-context.md.
    tasks = _topological_order(plan.get("tasks", []))
    ephemeral_agents = []

    abi_logging(f"[🔨] Creating workflow with {len(tasks)} tasks")

    # Find builder once (reused for all build tasks)
    builder_card = None
    needs_builder = any(
        t.get("type") in ("build_and_execute", "create_tools_and_execute")
        for t in tasks
    )
    if needs_builder:
        builder_card = await find_infra_agent("builder", plan_tasks=tasks)
        if not builder_card:
            return {"error": "Builder agent not found — cannot create ephemeral agents"}
        abi_logging(f"[🔧] Builder agent found: {builder_card.name}")

    # Find planner once (reused for all direct_tool tasks — see
    # .abi/specs/planner-direct-tool-pdf.md). The Planner executes these
    # itself; no Builder, no ephemeral container.
    planner_card = None
    needs_planner_direct = any(t.get("type") == "direct_tool" for t in tasks)
    if needs_planner_direct:
        planner_card = await find_infra_agent("planner", plan_tasks=tasks)
        if not planner_card:
            return {"error": "Planner agent not found — cannot execute direct_tool tasks"}
        abi_logging(f"[🔧] Planner agent found for direct_tool: {planner_card.name}")

    for task in tasks:
        tid = task.get("task_id")
        desc = task.get("description", "")
        task_type = task.get("type", "execute")
        target = task.get("target", {})

        # Collect artifact keys from dependency targets. The real upload
        # key is f"{agent_name}/{filename}" (see upload_workspace_artifacts)
        # — agent_name is the dependency's EPHEMERAL's dynamic name
        # (e.g. "ephemeral-task-1-1790724300"), only known after that
        # ephemeral was actually built, never at planning time. Using just
        # the bare filename tag here was the real bug: download_artifacts
        # always 404'd — invisible before because download_artifacts
        # itself didn't exist until today. Dependencies are processed
        # earlier in this same loop, so nodes[dep_id] (with the real
        # agent card) is already populated by the time we get here.
        dep_artifact_keys = []
        for dep_id in task.get("dependencies", []):
            dep_task = next((t for t in tasks if t.get("task_id") == dep_id), None)
            if dep_task and dep_task.get("target", {}).get("type") == "file":
                dep_tag = dep_task["target"]["tag"]
                dep_node = nodes.get(dep_id)
                if dep_node and dep_node.target_agent_card:
                    dep_artifact_keys.append(f"{dep_node.target_agent_card.name}/{dep_tag}")
                else:
                    abi_logging(
                        f"[⚠️] Task {tid}: dependency '{dep_id}' has no known "
                        "agent yet — skipping its artifact key"
                    )

        if task_type == "execute":
            agents = task.get("agents", [])
            if not agents or not agents[0]:
                abi_logging(f"[⚠️] Task {tid}: no agent assigned, skipping")
                continue

            agent_dict = agents[0]
            target = (
                build_agent_card(agent_dict)[0]
                if isinstance(agent_dict, dict)
                else agent_dict
            )

            # Health check before adding to workflow
            target_url = get_agent_url(target)
            if target_url:
                health = await AbiAgent.check_health(target_url, target.name)
                if health.get("status") not in ("healthy",):
                    abi_logging(
                        f"[❌] Task {tid}: agent '{target.name}' unreachable "
                        f"({health.get('status')}), attempting cleanup"
                    )
                    # Deregister only if it's NOT an infrastructure agent
                    agent_name_lower = target.name.lower()
                    is_infra = any(infra in agent_name_lower for infra in INFRA_AGENTS)
                    if not is_infra:
                        try:
                            toolkit = MCPToolkit()
                            dereg_result = await toolkit.call("unregister_agent", agent_name=target.name)
                            if isinstance(dereg_result, dict) and dereg_result.get("success"):
                                abi_logging(f"[🗑️] Deregistered stale agent '{target.name}'")
                            else:
                                abi_logging(f"[⚠️] Deregister failed for '{target.name}': {dereg_result}")
                        except Exception as e:
                            abi_logging(f"[⚠️] Deregister error for '{target.name}': {e}")
                    else:
                        abi_logging(f"[🛡️] Skipping deregister for infrastructure agent '{target.name}'")
                    continue

            abi_logging(f"[✅] Task {tid}: execute → {target.name}")

        elif task_type in ("build_and_execute", "create_tools_and_execute"):
            # Shallow copy — build_workflow gets called again per retry round
            # (see orchestrator.py's Phase 2.5 cascade) on the SAME task dict
            # objects (affected_tasks filters current_tasks by reference, it
            # doesn't copy them). Mutating task["builder_spec"] in place made
            # methodology_block get prepended again each round, on top of
            # what the previous round already prepended — confirmed live
            # 2026-09-30: a task retried 9 times carried 9 stacked copies of
            # the same boilerplate prefix ahead of its real instruction.
            builder_spec = dict(task.get("builder_spec", {}))
            # Pass artifact keys from dependencies and target tag
            if dep_artifact_keys:
                builder_spec["artifact_keys"] = dep_artifact_keys
            if target and target.get("tag"):
                builder_spec["target_tag"] = target["tag"]
            # The run's id names the code agent (ephemeral-<run_id>-…): the
            # A2A policy lets it talk only to its own run's reviewer.
            if plan_result.get("run_id"):
                builder_spec["run_id"] = plan_result["run_id"]
            # No methodology block for ephemerals: it is the Planner's framing,
            # not an instruction for writing a file; they get their role prompt
            # instead (ephemeral-reviewer-pipeline spec 04, decision 1).
            abi_logging(f"[🏗️] Task {tid}: {task_type} → calling builder (artifacts={dep_artifact_keys})")

            build_query = json.dumps({
                "task_id": tid,
                "task_type": task_type,
                "builder_spec": builder_spec,
                "description": desc,
                # process-awareness.md (Tier 3) — the plan-wide context_id
                # (not `tid`, which is per-task), so the spawned ephemeral
                # can read back the process_context blob the Orchestrator
                # wrote via update_session_context. See orchestrator.py's
                # stream(), right before this workflow runs.
                "context_id": context_id,
            })

            build_flow = AgentInteractionFlow()
            build_node = InteractionFlowNode(
                task=build_query,
                source_agent_card=AGENT_CARD,
                target_agent_card=builder_card,
                node_key=f"build_{tid}",
                node_label=f"Build agent for {tid}",
            )
            build_flow.add_node(build_node)
            build_flow.set_node_attributes(
                build_node.id,
                {"context_id": context_id, "task_id": task_id, "query": build_query},
            )
            build_flow.set_source_card(AGENT_CARD)

            build_results = []
            async for chunk in build_flow.run_workflow():
                build_results.append(chunk)

            builder_response = A2AResponse.find_plan(build_results)
            if not builder_response:
                for resp in A2AResponse.from_results(build_results):
                    if resp.data:
                        builder_response = resp.data
                        break
                    if resp.text:
                        try:
                            parsed = json.loads(resp.text)
                            if isinstance(parsed, dict) and ("agent" in parsed or "agent_card" in parsed):
                                builder_response = parsed
                                break
                        except (json.JSONDecodeError, TypeError):
                            pass

            if not builder_response or builder_response.get("status") == "error":
                error_msg = (
                    builder_response.get("message", "Builder failed")
                    if builder_response
                    else "No response from builder"
                )
                abi_logging(f"[❌] Task {tid}: builder failed — {error_msg}")
                continue

            ephemeral_agent = builder_response.get("agent", {})
            ephemeral_card_data = builder_response.get("agent_card", {})

            if not ephemeral_card_data:
                abi_logging(f"[❌] Task {tid}: builder returned no agent card")
                continue

            target = build_agent_card(ephemeral_card_data)[0]
            ephemeral_agents.append(ephemeral_agent)

            abi_logging(
                f"[✅] Task {tid}: ephemeral agent '{ephemeral_agent.get('name')}' "
                f"ready at {ephemeral_agent.get('url')}"
            )

        elif task_type == "direct_tool":
            # Fixed framework tool (e.g. write_pdf) — the Planner executes it
            # directly, no ephemeral agent. Structured JSON query (same
            # pattern as build_and_execute's build_query), not free text, so
            # the Planner's entrypoint can detect it deterministically before
            # running its normal planning DAG. See
            # .abi/specs/planner-direct-tool-pdf.md.
            direct_query = json.dumps({
                "_direct_tool": task.get("direct_tool"),
                "task_id": tid,
                "description": desc,
                "target_tag": target.get("tag") if target else None,
            })
            abi_logging(f"[⚡] Task {tid}: direct_tool='{task.get('direct_tool')}' → Planner")
            target = planner_card

        else:
            abi_logging(f"[⚠️] Task {tid}: unknown type '{task_type}', skipping")
            continue

        abi_logging(f"[✅] Task {tid}: assigned to agent '{target.name}' at {get_agent_url(target)} with prompt {desc}")
        if task_type == "direct_tool":
            # Structured JSON, not prose — the methodology block (free text)
            # doesn't apply here, the Planner's entrypoint parses this as JSON.
            node_desc = direct_query
        elif task_type in ("build_and_execute", "create_tools_and_execute"):
            node_desc = desc  # ephemerals: no methodology block (spec 04, decision 1)
        else:
            node_desc = methodology_block + desc if methodology_block else desc
        node = InteractionFlowNode(
            task=node_desc,
            source_agent_card=AGENT_CARD,
            target_agent_card=target,
            node_key=tid,
            node_label=f"{tid}: {desc[:40]}",
        )
        workflow.add_node(node)
        nodes[tid] = node
        workflow.set_node_attributes(
            node.id,
            {"task_id": task_id, "context_id": context_id, "query": node_desc},
        )

    # One add_edge call per target, with ALL its dependencies together —
    # NOT one call per dependency. LangGraph's add_edge only creates a true
    # "wait for all" join when the predecessors are passed as a single
    # list; calling it once per dependency (the previous code here) fires
    # the target once per call instead of once after all deps complete.
    # Reproduced live 2026-09-29 — see workflow.py::add_edge's docstring.
    for task in tasks:
        tid = task.get("task_id")
        if tid not in nodes:
            continue
        dep_ids = [nodes[dep].id for dep in task.get("dependencies", []) if dep in nodes]
        if dep_ids:
            workflow.add_edge(dep_ids if len(dep_ids) > 1 else dep_ids[0], nodes[tid].id)

    workflow.set_source_card(AGENT_CARD)

    if workflow.is_empty():
        abi_logging("[⚠️] Workflow is empty — no agents could be assigned")
        return {"error": "No agents could be assigned to execute the plan. Please try a different request."}

    return {
        "workflow": workflow,
        "plan": plan,
        "ephemeral_agents": ephemeral_agents,
        # deterministic-deliverable-contract-verification.md — so the
        # caller can check which real agent uploaded which artifact,
        # instead of trusting a flat, unindexed results list.
        "nodes": nodes,
    }


# ── Deterministic deliverable contract check ──────────────────────
# .abi/specs/not-implemented/deterministic-deliverable-contract-verification.md
#
# Reproduced live 2026-09-30: a 5-task workflow reported COMPLETED with
# zero real artifacts uploaded, and synthesis (free-text LLM generation)
# fabricated a full "success" summary instead of reporting the failure.
# These three functions verify by code — never by trusting the
# ephemeral's own "status": "completed" or asking an LLM to judge —
# whether each task's actual output satisfies what the Planner assigned
# it, before synthesis is ever allowed to run.

def _task_own_artifacts(tid: str, results: list, nodes: dict) -> list:
    """Artifacts uploaded specifically by this task's own ephemeral.

    `results` is a flat, unindexed list of every A2A chunk from every task
    in the workflow — matched here by agent name (`art["agent"]`, set by
    `upload_workspace_artifacts`) against `nodes[tid]`'s real, dynamically
    assigned agent card name.
    """
    from abi_core.common.a2a_response import A2AResponse

    node = nodes.get(tid)
    if not node or not getattr(node, "target_agent_card", None):
        return []
    agent_name = node.target_agent_card.name
    own = []
    for r in results:
        try:
            resp = A2AResponse.parse(r)
            if resp and resp.data:
                for art in resp.data.get("uploaded_artifacts", []):
                    if art.get("agent") == agent_name:
                        own.append(art)
        except Exception:
            pass
    return own


def _code_artifacts(artifacts: list) -> list:
    """The plan's .py files and README, one per filename (the latest — a
    Phase 2.5 retry re-uploads the same file)."""
    return [a for a in merge_artifacts([], artifacts)
            if a.get("filename", "").endswith(".py") or a.get("filename", "").lower().startswith("readme")]


async def _download_files(artifacts: list) -> dict:
    from abi_core.common.artifact_store import ArtifactStore

    store = ArtifactStore()
    files = {}
    for art in artifacts:
        key = art.get("key") or f"{art.get('agent', 'unknown')}/{art.get('filename', '')}"
        try:
            files[art["filename"]] = (await store.download(key)).decode("utf-8", errors="replace")
        except Exception as e:
            abi_logging(f"[⚠️] Integration review: could not download '{key}': {e}", level="warning")
    return files


# ── The run's reviewer (ephemeral-reviewer-pipeline 02.4) ──────
# The Orchestrator orchestrates and verifies; the reviewer repairs. Replaces
# the one-call repair the Orchestrator ran itself (repair_deliverables,
# 1.13.66–1.13.68), which broke "one entity, one task".

REVIEWED_TYPES = ("build_and_execute", "create_tools_and_execute")


def code_targets(plan: dict) -> list:
    """Files the plan's code agents deliver (code tasks with a target)."""
    return [(t.get("target") or {}).get("tag") for t in (plan or {}).get("tasks", [])
            if t.get("type") in REVIEWED_TYPES and (t.get("target") or {}).get("tag")]


def plan_needs_reviewer(plan: dict) -> bool:
    """Same threshold as the integration review: at least two .py files to
    integrate. A single-file plan has nothing to integrate."""
    return sum(1 for f in code_targets(plan) if f.endswith(".py")) >= 2


def _builder_response(results: list) -> dict:
    for resp in A2AResponse.from_results(results):
        if resp.data:
            return resp.data
        if resp.text:
            try:
                parsed = json.loads(resp.text)
                if isinstance(parsed, dict) and ("agent" in parsed or "agent_card" in parsed):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
    return {}


async def launch_reviewer(plan: dict, run_id: str, context_id: str, task_id: str) -> dict:
    """Ask the Builder for the run's reviewer, before any code agent, with
    retries (user decision, 2026-10-08). Returns its card (registered and
    healthy — the Builder health-checks it) or {} if it never got ready."""
    import asyncio
    import os

    attempts = int(os.getenv("REVIEWER_LAUNCH_ATTEMPTS", "3"))
    builder_card = await find_infra_agent("builder", plan_tasks=plan.get("tasks", []))
    if not builder_card:
        abi_logging("[❌] Reviewer: Builder agent not found", level="error")
        return {}
    build_query = json.dumps({
        "task_id": "reviewer",
        "task_type": "build_and_execute",
        "builder_spec": {"role": "reviewer", "run_id": run_id,
                         "system_prompt": f"Reviewer of plan run {run_id}"},
        "description": f"Reviewer of plan run {run_id}",
        "context_id": context_id,
    })
    for attempt in range(1, attempts + 1):
        flow = AgentInteractionFlow()
        node = InteractionFlowNode(task=build_query, source_agent_card=AGENT_CARD, target_agent_card=builder_card,
                                   node_key="build_reviewer", node_label="Build the run's reviewer")
        flow.add_node(node)
        flow.set_node_attributes(node.id, {"context_id": context_id, "task_id": task_id, "query": build_query})
        flow.set_source_card(AGENT_CARD)
        results = []
        try:
            async for chunk in flow.run_workflow():
                results.append(chunk)
        except Exception as e:
            abi_logging(f"[⚠️] Reviewer launch attempt {attempt}/{attempts} failed: {e}", level="warning")
        response = _builder_response(results)
        if response.get("status") == "ready" and response.get("agent_card"):
            abi_logging(f"[🔍] Reviewer ready: {response['agent_card'].get('name')} (attempt {attempt})")
            return response["agent_card"]
        abi_logging(f"[⚠️] Reviewer launch attempt {attempt}/{attempts}: "
                    f"{response.get('message') or 'no usable answer from the Builder'}", level="warning")
        if attempt < attempts:
            await asyncio.sleep(5)
    return {}


async def reviewer_request(reviewer_card: dict, body: dict, context_id: str):
    """One A2A request to the reviewer; yields its stream (statuses for the
    UI, then its answer)."""
    import uuid
    from abi_core.common.abi_a2a import agent_connection

    payload = {"message": {"role": "user", "parts": [{"kind": "text", "text": json.dumps(body)}],
                           "messageId": uuid.uuid4().hex, "contextId": context_id}}
    async for chunk in agent_connection(AGENT_CARD, build_agent_card(reviewer_card)[0], payload):
        yield chunk


async def run_files(run_id: str) -> dict:
    """The run's current set: code/ and docs/, with review/repaired/ on top."""
    from abi_core.common import project_store

    files = {}
    for area in ("code", "docs", "review/repaired"):
        for name in await project_store.list_area(run_id, area):
            files[name] = (await project_store.load(run_id, area, name)).decode("utf-8", errors="replace")
    return files


async def run_artifacts(run_id: str) -> list:
    """Download artifacts for the run's final files: the reviewer's version
    when there is one, else the code agent's."""
    from abi_core.common import project_store

    by_name = {}
    for area in ("code", "docs", "review/repaired"):
        for name in await project_store.list_area(run_id, area):
            by_name[name] = {"filename": name, "key": project_store.project_key(run_id, area, name),
                             "agent": "reviewer" if area == "review/repaired" else "code-agent"}
    return list(by_name.values())


async def verify_run(plan: dict, run_id: str):
    """Phase 2.5 + 2.6 on the run's folder: every deliverable exists, and the
    set works together (static + entry point in the governed sandbox).
    Returns (IntegrationReport or None, missing filenames)."""
    import os
    from abi_core.common.integration_review import review_files
    from abi_core.common.sandbox_service_client import sandbox_caller

    files = await run_files(run_id)
    missing = sorted(set(code_targets(plan)) - set(files))
    with sandbox_caller(run_id):
        report = await review_files(
            files, run_sandbox=os.getenv("INTEGRATION_REVIEW_SANDBOX", "true").strip().lower() == "true",
        )
    if report:
        abi_logging(f"[🔍] Verification: errors={len(report.errors)} missing={missing} "
                    f"sandbox={'yes' if report.layer2_ran else report.layer2_skipped}")
    return report, missing


async def review_with_reviewer(reviewer_card: dict, plan: dict, run_id: str, context_id: str, task_id: str,
                               run_with_heartbeat, agent_name: str):
    """The run's review loop (02.4): ask the reviewer for its report, verify
    it on the run's folder (2.5 + 2.6), send the findings back to the same
    reviewer — up to INTEGRATION_REPAIR_ROUNDS times — and finally tell it
    to leave. Yields AgentResponse statuses for the UI, then one tuple
    (IntegrationReport or None, missing filenames, the reviewer's last
    report or None)."""
    import os
    from abi_core.agent.agent import _HeartbeatDone
    from abi_core.agent.agent_response import AgentResponse, RunPhase

    def status(text, agent):
        return AgentResponse.status(text, agent=agent, context_id=context_id, task_id=task_id,
                                    phase=RunPhase.EXECUTING.value, phase_detail=text)

    max_rounds = int(os.getenv("INTEGRATION_REPAIR_ROUNDS", "3"))
    reviewer_name = reviewer_card.get("name", "reviewer")
    body = {"caller": "orchestrator"}
    integration, missing = None, []
    last_report = None
    review_round = 0
    while True:
        report = None
        try:
            async for chunk in reviewer_request(reviewer_card, body, context_id):
                resp = A2AResponse.parse(chunk)
                if resp and resp.data and resp.data.get("caller") == "reviewer":
                    report = resp.data
                text = (resp.text or resp.status_message) if resp else None
                if text and not (resp and resp.data):
                    yield status(text, reviewer_name)
        except Exception as e:
            abi_logging(f"[⚠️] Reviewer request failed: {e}", level="warning")
        if report:
            last_report = report
            abi_logging(
                f"[🔍] Reviewer report (round {report.get('round')}): repaired={sorted(report.get('repaired') or {})} "
                f"failed_agents={report.get('failed_agents')} missing_written={report.get('missing_written')}"
            )

        verify_note = "Verificando el trabajo del revisor..."
        yield status(verify_note, agent_name)
        async for item in run_with_heartbeat(verify_run(plan, run_id), context_id, task_id, verify_note,
                                             phase=RunPhase.EXECUTING.value):
            if isinstance(item, _HeartbeatDone):
                integration, missing = item.value
            else:
                yield item

        problems = bool(missing) or bool(integration and integration.errors)
        if not problems or report is None or review_round >= max_rounds:
            break
        review_round += 1
        errors_text = "\n".join(filter(None, [
            f"Missing deliverables (write them): {', '.join(missing)}" if missing else "",
            integration.as_text() if integration else "",
        ]))
        resend_note = (f"La verificación encontró problemas — se los reenvío al revisor "
                       f"(ronda {review_round}/{max_rounds})...")
        abi_logging(f"[🔍] {resend_note}")
        yield status(resend_note, agent_name)
        body = {"caller": "orchestrator", "errors": errors_text}

    # The reviewer leaves only on the Orchestrator's word — also after the
    # last round: the remaining findings go to the user.
    try:
        async for _ in reviewer_request(reviewer_card, {"caller": "orchestrator", "confirmed": True}, context_id):
            pass
    except Exception as e:
        abi_logging(f"[⚠️] Could not confirm to the reviewer ({e}); its own timeout ends it", level="warning")
    yield (integration, missing, last_report)


async def handoff_errors(run_id: str) -> list:
    """Code agents whose hand-off to the reviewer the A2A policy denied —
    each one records it in the run's folder (review/handoff-<task_id>.json)
    and ends instead of retrying."""
    from abi_core.common import project_store

    out = []
    try:
        for name in await project_store.list_area(run_id, "review"):
            if name.startswith("handoff-") and name.endswith(".json"):
                out.append(await project_store.load_json(run_id, "review", name))
    except Exception as e:
        abi_logging(f"[⚠️] Could not read hand-off errors for {run_id}: {e}", level="warning")
    return out


def reviewer_note(report: dict, handoffs: list = None) -> str:
    """What the user must know about how the files were produced — appended
    verbatim, never left to the synthesis model. Live 2026-10-09 all five
    code agents failed, the reviewer wrote every file, and the answer read
    as a normal success. Also the A2A policy denials between code agents and
    the reviewer (user decision 2026-10-10: stop at the first denial, go on,
    report it)."""
    lines = []
    labels = {"a2a_policy_denied": "la política A2A la negó",
              "a2a_invalid_request": "el mensaje fue rechazado como inválido"}

    def by_kind(items, key):
        groups = {}
        for it in items:
            groups.setdefault(it.get("kind", "a2a_policy_denied"), set()).add(it.get(key, "?"))
        return groups

    for kind, who in sorted(by_kind(handoffs or [], "task_id").items()):
        lines.append(f"⛔ Entrega al revisor fallida ({labels.get(kind, kind)}): "
                     f"{', '.join(sorted(who))}. El revisor trabajó sin su entrega.")
    for kind, who in sorted(by_kind((report or {}).get("communication_errors") or [], "to").items()):
        lines.append(f"⛔ El revisor no pudo preguntar ({labels.get(kind, kind)}) a: {', '.join(sorted(who))}.")
    if not report:
        return "\n".join(lines)
    failed = report.get("failed_agents") or []
    written = report.get("missing_written") or []
    if failed:
        lines.append(f"⚠️ Agentes de código que fallaron: {', '.join(failed)}.")
    if written:
        lines.append(f"✍️ Archivos escritos por el revisor (sus agentes no los entregaron): {', '.join(written)}.")
    return "\n".join(lines)


def merge_artifacts(current: list, repaired: list) -> list:
    """Replace files by name with the reviewer's versions; keep the rest."""
    by_name = {a.get("filename"): a for a in repaired}
    merged = [by_name.pop(a.get("filename"), a) for a in current]
    return merged + list(by_name.values())


async def review_deliverables(artifacts: list, run_id: str = None):
    """Phase 2.6 — do the delivered files work *together*?

    Phase 2.5 (check_deliverable_contracts) only proves each file exists.
    Reproduced live 2026-10-03: a 5-file Space Invaders plan passed 2.5,
    every file compiled, and the game crashed on its first frame
    (TypeError: 'EnemyFleet' has no len()) — and synthesis reported
    success. This downloads the plan's code files and runs the integration
    review: static checks (AST) + the entry point in the sandbox. No LLM
    involved. Returns an IntegrationReport, or None when there is nothing
    to integrate (< 2 .py files) or the review is disabled.

    INTEGRATION_REVIEW=false disables it; INTEGRATION_REVIEW_SANDBOX=false
    keeps only the static layer. See
    .abi/specs/not-implemented/sdd-pipeline/07-deliverable-integration-review.md

    `run_id` ties the sandbox run to this plan run: with
    SANDBOX_RUNTIME=service, sandbox-service only runs it for a known run,
    signed with the Orchestrator's card, and audits it in the run's project
    folder (ephemeral-reviewer-pipeline 02.5). Without it the service
    denies, and the review reports the execution as unverified.
    """
    import os
    if os.getenv("INTEGRATION_REVIEW", "true").strip().lower() != "true":
        return None

    def _wanted(name: str) -> bool:
        return name.endswith(".py") or name.lower().startswith("readme")

    wanted = [a for a in artifacts if _wanted(a.get("filename", ""))]
    if sum(1 for a in wanted if a["filename"].endswith(".py")) < 2:
        return None

    from abi_core.common.integration_review import review_files

    # Later artifacts win: a retried task re-uploads the same filename.
    files = await _download_files(_code_artifacts(artifacts))

    from contextlib import nullcontext
    from abi_core.common.sandbox_service_client import sandbox_caller

    try:
        with sandbox_caller(run_id) if run_id else nullcontext():
            report = await review_files(
                files,
                run_sandbox=os.getenv("INTEGRATION_REVIEW_SANDBOX", "true").strip().lower() == "true",
            )
    except Exception as e:
        abi_logging(f"[⚠️] Integration review failed (non-blocking): {e}", level="warning")
        return None

    if report:
        abi_logging(
            f"[🔍] Integration review: entry={report.entry_point} errors={len(report.errors)} "
            f"warnings={len(report.warnings)} sandbox={'yes' if report.layer2_ran else report.layer2_skipped}"
        )
        for f in report.errors:
            abi_logging(f"[🔍]   ❌ {f.as_text()}")
    return report


def check_deliverable_contracts(tasks: list, nodes: dict, results: list) -> list:
    """Which task_ids failed to produce their assigned file deliverable.

    A task with `target.type == "file"` must have uploaded an artifact
    whose filename matches `target.tag` — no LLM judgment involved. Tasks
    without a file target (e.g. `execute` against an existing agent) have
    nothing to verify here and are skipped.
    """
    failed = []
    for task in tasks:
        target = task.get("target") or {}
        if target.get("type") != "file":
            continue
        tid = task.get("task_id")
        tag = target.get("tag")
        own_artifacts = _task_own_artifacts(tid, results, nodes)
        if not any(a.get("filename") == tag for a in own_artifacts):
            failed.append(tid)
    return failed


def transitive_dependents(failed_ids: list, tasks: list) -> set:
    """Every task that depends on any of `failed_ids`, directly or through
    another already-affected task.

    Integrity rule confirmed with the user, 2026-09-30: a rebuilt
    dependency invalidates everything downstream of it, whether or not its
    real contract (extract_python_contract) actually changed — no
    comparison, no exception.
    """
    affected = set(failed_ids)
    changed = True
    while changed:
        changed = False
        for task in tasks:
            tid = task.get("task_id")
            if tid in affected:
                continue
            deps = task.get("dependencies", [])
            if any(d in affected for d in deps):
                affected.add(tid)
                changed = True
    return affected
