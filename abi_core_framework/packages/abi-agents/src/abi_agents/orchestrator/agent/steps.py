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

import json

from app import agent
from abi_core.common.utils import abi_logging, format_plan_summary, format_conversation_summary
from abi_core.common.a2a_response import A2AResponse
from abi_core.common.semantic_tools import tool_find_agent, MCPToolkit
from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode
from a2a.types import AgentCard
from abi_core.common.agent_card_loader import build_agent_card, get_agent_url
from abi_core.agent.agent import AbiAgent
from config import AGENT_CARD, config

# Agents that must NEVER be deregistered (infrastructure)
INFRA_AGENTS = {"builder", "planner", "orchestrator", "guardian", "semantic-layer"}

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
        return sentinel_result

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
        guardian_card = await tool_find_agent.ainvoke({"query": "guardian"})
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
        valid_actions = ["resolve_pending_plan", "answer_directly"]
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

    planner_card = await tool_find_agent.ainvoke({"query": "planner"})
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
    methodology_block = f"[Metodología del plan: {methodology}] {rationale}\n\n" if methodology else ""
    workflow = AgentInteractionFlow()
    nodes = {}
    tasks = plan.get("tasks", [])
    ephemeral_agents = []

    abi_logging(f"[🔨] Creating workflow with {len(tasks)} tasks")

    # Find builder once (reused for all build tasks)
    builder_card = None
    needs_builder = any(
        t.get("type") in ("build_and_execute", "create_tools_and_execute")
        for t in tasks
    )
    if needs_builder:
        builder_card = await tool_find_agent.ainvoke({"query": "builder"})
        if not builder_card:
            return {"error": "Builder agent not found — cannot create ephemeral agents"}
        abi_logging(f"[🔧] Builder agent found: {builder_card.name}")

    # Find planner once (reused for all direct_tool tasks — see
    # .abi/specs/planner-direct-tool-pdf.md). The Planner executes these
    # itself; no Builder, no ephemeral container.
    planner_card = None
    needs_planner_direct = any(t.get("type") == "direct_tool" for t in tasks)
    if needs_planner_direct:
        planner_card = await tool_find_agent.ainvoke({"query": "planner"})
        if not planner_card:
            return {"error": "Planner agent not found — cannot execute direct_tool tasks"}
        abi_logging(f"[🔧] Planner agent found for direct_tool: {planner_card.name}")

    for task in tasks:
        tid = task.get("task_id")
        desc = task.get("description", "")
        task_type = task.get("type", "execute")
        target = task.get("target", {})

        # Collect artifact keys from dependency targets
        dep_artifact_keys = []
        for dep_id in task.get("dependencies", []):
            dep_task = next((t for t in tasks if t.get("task_id") == dep_id), None)
            if dep_task and dep_task.get("target", {}).get("type") == "file":
                dep_tag = dep_task["target"]["tag"]
                # Key format matches what synthesize_and_report uploads
                dep_artifact_keys.append(dep_tag)

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
            builder_spec = task.get("builder_spec", {})
            # Pass artifact keys from dependencies and target tag
            if dep_artifact_keys:
                builder_spec["artifact_keys"] = dep_artifact_keys
            if target and target.get("tag"):
                builder_spec["target_tag"] = target["tag"]
            if methodology_block:
                builder_spec["system_prompt"] = methodology_block + builder_spec.get("system_prompt", "")
            abi_logging(f"[🏗️] Task {tid}: {task_type} → calling builder (artifacts={dep_artifact_keys})")

            build_query = json.dumps({
                "task_id": tid,
                "task_type": task_type,
                "builder_spec": builder_spec,
                "description": desc,
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

    for task in tasks:
        tid = task.get("task_id")
        for dep in task.get("dependencies", []):
            if dep in nodes and tid in nodes:
                workflow.add_edge(nodes[dep].id, nodes[tid].id)
                abi_logging(f"[🔗] Edge: {dep} → {tid}")

    workflow.set_source_card(AGENT_CARD)

    if workflow.is_empty():
        abi_logging("[⚠️] Workflow is empty — no agents could be assigned")
        return {"error": "No agents could be assigned to execute the plan. Please try a different request."}

    return {
        "workflow": workflow,
        "plan": plan,
        "ephemeral_agents": ephemeral_agents,
    }
