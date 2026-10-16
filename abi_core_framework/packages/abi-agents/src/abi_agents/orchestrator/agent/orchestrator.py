import asyncio
import json
from collections.abc import AsyncIterable

from abi_core.common.utils import abi_logging, build_plan_view, format_plan_summary
from abi_core.common.workflow import Status
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent, _HeartbeatDone
from abi_core.agent.agent_response import AgentResponse, RunPhase
from abi_core.agent.routing_tools import build_routing_decision_schema, format_system_state
from abi_core.memory import MEMORY_TOOLS, add_long_term_memory

from config import config


class AbiOrchestratorAgent(AbiAgent):
    """Orchestrator Agent — coordinates multi-agent workflows.

    Ephemeral agents self-deregister and self-destroy via self_deregister().
    The orchestrator is NOT responsible for ephemeral lifecycle.

    Routing (is this a new request? a reply to a pending plan/clarification?
    just chat?) is decided by the LLM's own reasoning turn, not by a
    deterministic code gate — see
    .abi/specs/orchestrator-unified-routing-contract.md. A deterministic step
    (steps.py::build_routing_contract) always assembles the same contract
    shape first (pending state + the menu of valid actions for this turn);
    the LLM's turn then has two phases: optional tool-calling to gather
    context (this agent's tools below), then a mandatory structured decision
    forced to one of the contract's valid_actions (orchestrator.py::
    _reasoning_turn) — no "the LLM didn't choose" outcome is possible at the
    schema level. Only sentinels (button clicks, steps.py::classify_query)
    and Guardian stay fully deterministic, ahead of any LLM freedom.
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[tool_find_agent, *MEMORY_TOOLS],
            system_prompt=config.SYSTEM_PROMPT,
            content_types=['text', 'text/plain'],
        )

    async def _record_pending_clarification(
        self, context_id: str, original_query: str, clarification: str
    ):
        """Record a pending clarification as a system-level event in memory.

        This is a *system* event (not agent state): it lives in short-term
        memory so that the next user message in this session is recognized as
        the answer to the clarification — regardless of whether the orchestrator
        process restarts between turns. Best effort: a memory failure does not
        block emitting the clarification to the user.
        """
        if not config.AGENT_MEMORY_URL or not context_id:
            return
        try:
            from abi_core.memory import add_short_term_memory

            # The marker substring "pending_clarification" must appear in the
            # stored text so the triage step can detect it on the next turn.
            payload = json.dumps({
                "_event": "pending_clarification",
                "original_query": original_query,
                "clarification": clarification,
            })
            await add_short_term_memory(
                topic="pending_clarification",
                task=context_id,
                content=payload,
                context_id=context_id,
                memory_url=config.AGENT_MEMORY_URL,
            )
            abi_logging(f"[📝] Pending clarification recorded for session {context_id}")
        except Exception as e:
            abi_logging(f"[⚠️] Could not record pending clarification: {e}")

    async def _record_plan_methodology(self, context_id: str, plan: dict):
        """The plan's methodology is *system* context: it should be visible
        to any agent that inspects this conversation, not just whichever
        agent happens to receive the prompt directly (Local vs Global —
        avoids the plan's methodology getting lost to context degradation
        as it crosses agents). Best-effort, same as _record_pending_clarification.

        Swarm-specific (AMS-backed) — the generic "record this plan as
        pending" bookkeeping is ``self.record_pending_plan``, inherited from
        AbiAgent. See .abi/specs/agent-session-bookkeeping-methods.md.
        """
        methodology = plan.get("methodology")
        if methodology and config.AGENT_MEMORY_URL:
            try:
                from abi_core.memory import add_short_term_memory

                await add_short_term_memory(
                    topic="plan_methodology",
                    task=context_id,
                    content=json.dumps({
                        "methodology": methodology,
                        "rationale": plan.get("methodology_rationale", ""),
                    }),
                    context_id=context_id,
                    memory_url=config.AGENT_MEMORY_URL,
                )
            except Exception as e:
                abi_logging(f"[⚠️] Could not record plan methodology in system memory: {e}")

    async def _clear_pending_clarification(self, context_id: str) -> None:
        """Mark the pending clarification resolved. Called ONLY when the
        reasoning turn actually invokes resolve_pending_clarification — never
        just because a message arrived while one was pending (that was the
        root cause of the "no hablo ingles" bug)."""
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

    async def _reasoning_turn(self, contract: dict, context_id: str, task_id: str, result_holder: dict):
        """Two-phase turn — see .abi/specs/orchestrator-unified-routing-contract.md.

        Phase 1 (skipped when resolve_pending_plan is on the table — see
        below): bounded tool-calling with this agent's own tools
        (tool_find_agent, MEMORY_TOOLS only — routing is no longer
        tool-calling based) so the LLM can gather context before committing
        to a routing decision. A tool call does not stop this loop; it keeps
        going until the model produces plain text (or the graph's own
        recursion limit is hit).

        Phase 2 (replaces the old tool-calling routing turn +
        _should_have_delegated/_enforce_create_plan safety net): ONE
        `with_structured_output` call, forced to `contract["valid_actions"]`
        via a dynamic Literal schema (abi_core.agent.routing_tools). There is
        no "the LLM didn't choose" outcome possible at the schema level —
        `tool_choice="required"` was the original plan but is a documented
        no-op for Ollama, verified against the installed langchain-ollama
        source before switching to this approach.

        Uses a fresh thread per call (task_id, not context_id) for phase 1 —
        this turn is deliberately stateless in LangGraph's own terms. All
        cross-turn state (pending plan/clarification) is already
        reconstructed deterministically every turn via `contract` (Local vs
        Global — see .abi/WORKING_RULES.md).
        """
        query = contract["query"]
        resolving_pending_plan = "resolve_pending_plan" in contract["valid_actions"]

        # ── Phase 1: optional context-gathering ──────────────────────
        # Skipped for resolve_pending_plan: deciding whether "apruebo el
        # plan" means approve/reject/modify never needs memory/agent lookup
        # context, and running it anyway was actively harmful — verified
        # live: a failed memory-tool attempt produced a confused narrative
        # ("I will attempt to write the file manually...") that, once fed
        # into phase 2's prompt as gathered context, pushed the model to
        # choose action=create_plan and ignore the pending plan entirely.
        # Also costs 40+ seconds for zero benefit in this case.
        gathered_context = ""
        if not resolving_pending_plan:
            inputs = {"messages": [{"role": "user", "content": query}]}
            thread_config = {"configurable": {"thread_id": f"{context_id}:{task_id}"}}
            async for chunk in self.agent.astream(
                inputs, config=thread_config, stream_mode="updates"
            ):
                for _node, node_data in chunk.items():
                    for msg in node_data.get("messages", []):
                        if getattr(msg, "content", None) and not getattr(msg, "tool_calls", None):
                            gathered_context = msg.content

        # ── Phase 2: mandatory structured routing decision ───────────
        # resolve_pending_plan is the highest-stakes decision here — a
        # false "approve" triggers real build_workflow/Docker execution.
        # Profiled empirically: config.MODEL_NAME's default gets this wrong
        # ~60% of the time regardless of schema shape; a bigger model alone
        # doesn't fix it either (capability profile, not size — see
        # .abi/specs/orchestrator-unified-routing-contract.md). Use the
        # profiled-better model ONLY for this decision, not every turn —
        # the other actions already work reliably on the default model.
        if resolving_pending_plan:
            from abi_core.agent.llm_provider import create_llm
            decision_llm = create_llm(config.ROUTING_DECISION_LLM_CONFIG)
        else:
            decision_llm = self.llm

        schema = build_routing_decision_schema(contract["valid_actions"])
        structured_llm = decision_llm.with_structured_output(schema, method="json_schema")

        system_state = format_system_state(
            contract.get("pending_plan_summary"),
            contract.get("pending_clarification_question"),
            contract.get("recent_conversation_summary"),
        )
        prompt = config.build_routing_decision_prompt(system_state, query, gathered_context)

        # This call has NO system prompt otherwise (decision_llm is the bare
        # model, not self.agent — config.SYSTEM_PROMPT never reaches it) —
        # see config.build_routing_decision_system_message's own docstring
        # (agent/prompts.py) for the failure modes this framing fixes.
        from langchain_core.messages import SystemMessage, HumanMessage

        system_message = config.build_routing_decision_system_message()
        messages = [SystemMessage(content=system_message), HumanMessage(content=prompt)]

        try:
            result_holder["decision"] = await structured_llm.ainvoke(messages)
        except Exception as e:
            # The one genuine recovery path this design needs — a real
            # protocol/parse failure, not a judgment call. stream()'s outer
            # except also catches this, but logging here keeps the
            # structured-output failure distinguishable from other errors.
            abi_logging(f"[⚠️] Structured routing decision failed to parse: {e}", level="warning")
            result_holder["decision"] = None

    async def _call_planner_and_respond(self, query: str, context_id: str, task_id: str):
        """Call the Planner, then ask for clarification / surface an error /
        record the pending plan and ask for confirmation.

        Replaces the old DAG chain call_planner -> extract_plan ->
        check_model_availability — now plain function calls (steps.py,
        tools.py), since the decision to reach this point comes from the
        reasoning turn (a tool call), not from the DAG itself.
        """
        from steps import call_planner, extract_plan
        from tools import check_model_availability

        yield AgentResponse.status(
            "Calling planner...", agent=self.agent_name, context_id=context_id, task_id=task_id,
            phase=RunPhase.PLANNING.value,
        )
        planner_results = None
        async for item in self._run_with_heartbeat(
            call_planner(query, context_id, task_id), context_id, task_id, "Planning...",
            phase=RunPhase.PLANNING.value,
        ):
            if isinstance(item, _HeartbeatDone):
                planner_results = item.value
            else:
                yield item
        plan_result = extract_plan(planner_results)

        if "clarification" in plan_result:
            abi_logging("[❓] Forwarding clarification request to user")
            await self._record_pending_clarification(context_id, query, plan_result["clarification"])
            clarification_text = (
                f"🤔 **Necesito mas informacion para crear el mejor plan:**\n\n{plan_result['clarification']}"
            )
            await self.record_conversation_turn(
                context_id, query, clarification_text, window=config.CONVERSATION_WINDOW
            )
            yield AgentResponse.input_required(
                clarification_text,
                questions=plan_result.get("questions", []),
            )
            return

        if "error" in plan_result:
            await self.record_error(context_id, "plan_error", plan_result["error"])
            await self.record_conversation_turn(
                context_id, query, plan_result["error"], window=config.CONVERSATION_WINDOW
            )
            yield AgentResponse.error(plan_result["error"])
            return

        plan = plan_result["plan"]
        model_status_result = await check_model_availability(plan_result)
        model_status = (
            model_status_result.get("model_status", {})
            if isinstance(model_status_result, dict) else {}
        )
        summary = format_plan_summary(plan, model_status)
        await self.record_pending_plan(context_id, plan, query)
        await self._record_plan_methodology(context_id, plan)
        await self.record_conversation_turn(context_id, query, summary, window=config.CONVERSATION_WINDOW)
        # `summary` stays the text contract (routing LLM, memory, text-only
        # clients); `plan_view` is structured data for the review card —
        # see .abi/specs/not-implemented/ux/chainlit-plan-review-card.md.
        yield AgentResponse.input_required(
            summary, action_type="plan_confirmation",
            plan_view=build_plan_view(plan, model_status),
        )

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, any]]:
        """Orchestrate workflow execution using the task DAG."""

        abi_logging(f'[*] Orchestrator stream - context: {context_id}, task: {task_id}')
        abi_logging(f'[📝] Query: {query}')

        if not query:
            raise ValueError('Please provide a Query')

        try:
            if self.tool_graph is None:
                yield AgentResponse.error("No tool_graph configured")
                return

            # ── Phase 1: Triage + Guardian + Planning pipeline (DAG) ──
            yield AgentResponse.status(
                "Analyzing request...",
                agent=self.agent_name,
                context_id=context_id,
                task_id=task_id,
                phase=RunPhase.ANALYZING.value,
            )

            session_ctx = await self.get_session_context(context_id)
            dag_coro = self.tool_graph.execute({
                "query": query,
                "context_id": context_id,
                "task_id": task_id,
                "session_context": session_ctx,
            })
            dag_result = None
            async for item in self._run_with_heartbeat(
                dag_coro, context_id, task_id, "Processing...", phase=RunPhase.ANALYZING.value,
            ):
                if isinstance(item, _HeartbeatDone):
                    dag_result = item.value
                else:
                    yield item

            if dag_result.get("failed_node"):
                error = dag_result.get("error", "Pipeline failed")
                abi_logging(f"[❌] DAG failed at {dag_result['failed_node']}: {error}")
                await self.record_error(context_id, "dag_failed", error)
                yield AgentResponse.error(error)
                return

            outputs = dag_result.get("node_outputs", {})

            # ── Check gate decision ──────────────────────────────
            gate = outputs.get("gate_decision", {})
            action = gate.get("action", "") if isinstance(gate, dict) else ""
            abi_logging(f"[🚦] Gate decision: action={action}, outputs_keys={list(outputs.keys())}")

            if action == "system_error":
                await self.record_error(context_id, "guardian_failed", gate.get("message", ""))
                yield AgentResponse.error(gate.get("message", "System error"))
                return

            if action == "blocked":
                await self.record_error(context_id, "blocked", gate.get("message", ""))
                yield AgentResponse.error(gate.get("message", "Request blocked"))
                return

            # ── Plan confirmation replies via sentinel (button click) ──
            if action == "plan_confirmation_orphaned":
                # Looked like a confirm/reject/modify reply, but no pending
                # plan exists in this session — usually lost session
                # continuity (no token → fresh anonymous context per
                # request). Say so instead of silently planning around the
                # literal reply text.
                from abi_core.agent.plan_confirmation import ORPHANED_CONFIRMATION_MESSAGE
                yield AgentResponse.text(ORPHANED_CONFIRMATION_MESSAGE)
                return

            if action == "plan_rejected":
                await self.clear_pending_plan(context_id)
                rejection_text = "Plan cancelado. Decime si querés que arme uno nuevo."
                await self.record_conversation_turn(
                    context_id, query, rejection_text, window=config.CONVERSATION_WINDOW
                )
                yield AgentResponse.text(rejection_text)
                return

            if action == "plan_modify_requested":
                await self.update_session_context(context_id, {"awaiting_plan_modification": True})
                modify_text = "¿Qué te gustaría cambiar del plan?"
                await self.record_conversation_turn(
                    context_id, query, modify_text, window=config.CONVERSATION_WINDOW
                )
                yield AgentResponse.input_required(modify_text)
                return

            if action == "plan_modification_feedback":
                # Deterministic twin of the reasoning turn's
                # resolve_pending_plan+modify branch below (steps.py::
                # classify_query) — bypasses the LLM routing decision
                # entirely. awaiting_plan_modification was set by code
                # right before asking "¿qué querés cambiar?", so this
                # reply is unambiguously the feedback. Reproduced live
                # 2026-09-29: the reasoning turn picked answer_directly
                # (a dead end, no Planner call) instead of
                # resolve_pending_plan for this exact case.
                await self.update_session_context(context_id, {"awaiting_plan_modification": False})
                feedback = gate.get("feedback", query)
                enriched = f"{session_ctx.get('pending_plan_query', '')}\n\nCambios solicitados: {feedback}"
                async for r in self._call_planner_and_respond(enriched, context_id, task_id):
                    yield r
                return

            if action == "clarification_answered":
                # Deterministic twin of the reasoning turn's
                # resolve_pending_clarification branch below — same
                # enriched-query construction, but the "does this answer my
                # pending clarification?" decision was never asked of an
                # LLM: the form submission itself is the proof. See
                # .abi/specs/deterministic-clarification-answers.md.
                await self._clear_pending_clarification(context_id)
                pending_clarification = gate.get("pending_clarification") or {}
                original = pending_clarification.get("original_query", "")
                answers = gate.get("answers", {})
                answers_text = "\n".join(f"{qid}: {ans}" for qid, ans in answers.items())
                enriched = f"{original}\n\nUser clarification:\n{answers_text}" if original else answers_text
                async for r in self._call_planner_and_respond(enriched, context_id, task_id):
                    yield r
                return

            stored_plan = None
            run_confirmed_plan = False

            if action == "execute_confirmed_plan":
                stored_plan = gate.get("plan")
                run_confirmed_plan = True

            elif action == "reasoning_turn":
                # ── Everything else: new request, reply to a pending plan/
                # clarification, or simple chat. A deterministic contract
                # (same shape regardless of scenario) is built first, then
                # the LLM's reasoning turn commits to exactly one of its
                # valid_actions — see
                # .abi/specs/orchestrator-unified-routing-contract.md.
                from steps import build_routing_contract

                pending_clarification = gate.get("pending_clarification") or {}
                contract = build_routing_contract(query, session_ctx, pending_clarification)
                # Consume-on-read: shows up in the contract exactly once (the
                # turn right after a failure), then never again — no TTL,
                # no timestamp. See .abi/specs/orchestrator-last-error-awareness.md.
                if session_ctx.get("last_error"):
                    await self.update_session_context(context_id, {"last_error": None})

                result_holder = {}
                async for item in self._run_with_heartbeat(
                    self._reasoning_turn(contract, context_id, task_id, result_holder),
                    context_id, task_id, "Thinking...", phase=RunPhase.ROUTING.value,
                ):
                    if not isinstance(item, _HeartbeatDone):
                        yield item

                decision = result_holder.get("decision")

                if decision is None:
                    # Genuine protocol/parse failure — the one recovery path
                    # this design needs (see _reasoning_turn's docstring).
                    abi_logging(
                        "[⚠️] Structured routing decision missing — "
                        f"valid_actions={contract['valid_actions']}",
                        level="warning",
                    )
                    yield AgentResponse.text("No pude interpretar tu respuesta. ¿Podés reformularla?")
                    return

                # Discriminated union (see
                # .abi/specs/implemented/routing-decision-discriminated-union.md) —
                # `decision.outcome` is one of the per-action models, never a
                # flat bag of every action's fields at once. Whichever
                # `.action` it is, the OTHER actions' fields don't exist on
                # it at all (not just empty) — structurally impossible for
                # the model to write real content into the wrong field.
                outcome = decision.outcome
                # Which action the model committed to was never logged —
                # reproduced live 2026-10-03: six build requests in a row got
                # answer_directly (copied verbatim from a prior turn in the
                # conversation history) and nothing after "Gate decision"
                # showed it; had to be reconstructed from Redis.
                abi_logging(
                    f"[🧭] Routing decision: action={outcome.action} "
                    f"valid={contract['valid_actions']} "
                    f"history_turns={len(session_ctx.get('conversation_summary') or [])} "
                    f"detail={(getattr(outcome, 'objective', None) or getattr(outcome, 'decision', None) or getattr(outcome, 'text', None) or '')[:120]!r}"
                )

                if outcome.action == "create_plan":
                    # The user's own words, kept for the synthesis after the
                    # run: the Planner only gets the routing's rewrite of
                    # them (outcome.objective, usually English), which made
                    # every synthesis answer in English.
                    await self.update_session_context(context_id, {"plan_user_message": query})
                    async for r in self._call_planner_and_respond(outcome.objective or query, context_id, task_id):
                        yield r
                    return

                if outcome.action == "resolve_pending_clarification":
                    await self._clear_pending_clarification(context_id)
                    original = pending_clarification.get("original_query", "")
                    answer = outcome.answer or query
                    enriched = f"{original}\n\nUser clarification: {answer}" if original else answer
                    async for r in self._call_planner_and_respond(enriched, context_id, task_id):
                        yield r
                    return

                if outcome.action == "resolve_pending_plan":
                    if outcome.decision == "approve":
                        stored_plan = session_ctx.get("pending_plan")
                        run_confirmed_plan = True
                    elif outcome.decision == "reject":
                        await self.clear_pending_plan(context_id)
                        yield AgentResponse.text("Plan cancelado. Decime si querés que arme uno nuevo.")
                        return
                    elif outcome.decision == "modify":
                        feedback = outcome.feedback
                        if not feedback:
                            await self.update_session_context(context_id, {"awaiting_plan_modification": True})
                            yield AgentResponse.input_required("¿Qué te gustaría cambiar del plan?")
                            return
                        enriched = f"{session_ctx.get('pending_plan_query', '')}\n\nCambios solicitados: {feedback}"
                        async for r in self._call_planner_and_respond(enriched, context_id, task_id):
                            yield r
                        return
                    else:
                        # decision field is Optional — model committed to
                        # resolve_pending_plan (the outer action, reliable in
                        # practice) but not to which sub-decision (observed
                        # empirically to be less reliable on qwen3:latest — see
                        # .abi/specs/orchestrator-unified-routing-contract.md,
                        # "Lo que esto NO resuelve"). Logged, not silent —
                        # a fallback to text=None here would hide exactly
                        # the residual risk that spec already flags.
                        abi_logging(
                            f"[⚠️] resolve_pending_plan chosen but decision sub-field empty for query={query!r}",
                            level="warning",
                        )
                        yield AgentResponse.text("No pude interpretar tu respuesta. ¿Podés reformularla?")
                        return

                if outcome.action == "answer_directly":
                    answer_text = outcome.text or "No pude interpretar tu respuesta. ¿Podés reformularla?"
                    await self.record_conversation_turn(
                        context_id, query, answer_text, window=config.CONVERSATION_WINDOW
                    )
                    yield AgentResponse.text(answer_text)
                    return

            if run_confirmed_plan:
                if not stored_plan:
                    yield AgentResponse.error(
                        "El plan pendiente ya no está disponible (la sesión pudo haber expirado). "
                        "Por favor volvé a describir tu solicitud."
                    )
                    return
                await self.clear_pending_plan(context_id)
                from steps import build_workflow, launch_reviewer, plan_needs_reviewer

                # context_id is the CONVERSATION's id, not this plan's: every
                # plan in the same chat shares it, and every plan names its
                # tasks task_1..task_N. Found 2026-10-03: two Space Invaders
                # runs in one chat wrote their inter-task contracts to the
                # same keys. run_id scopes contracts — and the project folder
                # — to this plan run; written once, here, before any agent
                # exists (the reviewer needs it at creation).
                import uuid
                run_id = uuid.uuid4().hex[:12]

                # Project folder for this run (ephemeral-reviewer-pipeline
                # 02.1): the plan as the Planner sent it, technical design
                # inside.
                try:
                    from abi_core.common import project_store
                    key = await project_store.save_json(run_id, "plan", "plan.json", stored_plan)
                    abi_logging(f"[📁] Project folder: {key}")
                except Exception as e:
                    abi_logging(f"[⚠️] Could not write plan to project folder: {e}", level="warning")

                # The run's reviewer first (02.4, user decision 2026-10-08):
                # with retries; code agents are created only once it is
                # ready, or not at all.
                reviewer_card = {}
                if plan_needs_reviewer(stored_plan):
                    yield AgentResponse.status(
                        "Creando el revisor del plan...", agent=self.agent_name,
                        context_id=context_id, task_id=task_id, phase=RunPhase.BUILDING.value,
                    )
                    async for item in self._run_with_heartbeat(
                        launch_reviewer(stored_plan, run_id, context_id, task_id), context_id, task_id,
                        "Creando el revisor del plan...", phase=RunPhase.BUILDING.value,
                    ):
                        if isinstance(item, _HeartbeatDone):
                            reviewer_card = item.value or {}
                        else:
                            yield item
                    if not reviewer_card:
                        msg = "No se pudo crear el revisor del plan, así que no se lanzaron los agentes de código."
                        await self.record_error(context_id, "reviewer_launch_failed", msg)
                        yield AgentResponse.error(msg)
                        return

                # process-awareness.md (Tier 3): one write, keyed by this
                # plan's context_id — every ephemeral reads it back via
                # get_session_context. `reviewer` tells code agents there is
                # one and whom to hand their work to (02.2).
                stored_tasks = stored_plan.get("tasks", [])
                await self.update_session_context(context_id, {
                    "process_context": {
                        "run_id": run_id,
                        "reviewer": reviewer_card.get("name"),
                        "objective": stored_plan.get("objective", ""),
                        "total_tasks": len(stored_tasks),
                        "tasks": [
                            {
                                "task_id": t.get("task_id", "?"),
                                "description": t.get("description", "")[:100],
                                "dependencies": t.get("dependencies", []),
                            }
                            for t in stored_tasks
                        ],
                    },
                })

                yield AgentResponse.status(
                    "Preparing agents...", agent=self.agent_name,
                    context_id=context_id, task_id=task_id, phase=RunPhase.BUILDING.value,
                )
                build_result = await build_workflow({"plan": stored_plan, "run_id": run_id}, context_id, task_id)

                if "gate_passthrough" in build_result:
                    yield AgentResponse.error(build_result["gate_passthrough"].get("message", "Unexpected gate passthrough"))
                    return
                if "error" in build_result:
                    await self.record_error(context_id, "plan_error", build_result["error"])
                    yield AgentResponse.error(build_result["error"])
                    return

            # ── Phase 2: Execute agent workflow ──────────────────
            workflow = build_result.get("workflow")
            plan = build_result.get("plan", {})

            if not workflow or workflow.is_empty():
                msg = "No agents could be assigned to execute the plan."
                await self.record_error(context_id, "empty_workflow", msg)
                yield AgentResponse.error(msg)
                return

            # Log execution plan summary
            tasks = plan.get("tasks", [])

            abi_logging(f"[📋] Executing plan: '{plan.get('objective', '')}' — {len(tasks)} tasks")
            for t in tasks:
                tid = t.get("task_id", "?")
                ttype = t.get("type", "?")
                desc = t.get("description", "")[:100]
                agent_name = ""
                if t.get("agents"):
                    a = t["agents"][0]
                    agent_name = a.get("name", "?") if isinstance(a, dict) else str(a)
                abi_logging(f"[📋]   {tid} [{ttype}] → {agent_name or 'pending'} | {desc}")

            from abi_core.common.a2a_response import A2AResponse

            def _task_meta(task_list):
                # Same execution-order numbering and titles as the plan
                # review card, so "paso 2 de 5" is row 2 of what the user
                # approved.
                steps = {s["task_id"]: s for s in build_plan_view({"tasks": task_list})["steps"]}
                step = steps.get(workflow.current_node_key) or {}
                # Independent tasks run in parallel: say which ones are
                # still running, not just which one sent this update.
                running = [k for k in workflow.running_node_keys if k in steps]
                return {
                    "phase": RunPhase.EXECUTING.value,
                    "task_key": workflow.current_node_key,
                    "task_label": step.get("title") or workflow.current_node_label,
                    "task_index": step.get("index"),
                    "task_total": len(task_list),
                    "task_deliverable": (step.get("deliverable") or {}).get("tag"),
                    "running_task_keys": running,
                    "running_task_indices": sorted(steps[k]["index"] for k in running),
                }

            results = []
            async for chunk in workflow.run_workflow():
                results.append(chunk)
                resp = A2AResponse.parse(chunk)
                # `resp.status_message` — not just `resp.text` — because a
                # heartbeat ("Executing pipeline...", emitted every 15s by
                # the ephemeral's own _run_with_heartbeat) arrives as a
                # status_update event, and A2AResponse.parse() puts THAT
                # text in status_message, not text (text is only populated
                # for artifact/message events). Confirmed live 2026-10-01:
                # heartbeats were firing exactly every 15s the whole time,
                # silently dropped right here because this check only ever
                # looked at resp.text — a 16-minute real task showed zero
                # intermediate UI updates and ended in Chainlit's own
                # "No response received." despite the backend working the
                # entire time. See .abi/specs/not-implemented/
                # orchestrator-drops-status-update-heartbeats.md.
                text = (resp.text or resp.status_message) if resp else None
                if text:
                    yield AgentResponse.status(
                        text, agent=workflow.current_agent_name or self.agent_name,
                        context_id=context_id, task_id=task_id,
                        phase_detail=text, **_task_meta(tasks),
                    )
                # else: intermediate A2A protocol event with no user-facing
                # text (e.g. a raw StreamResponse) — skip it. Yielding the raw
                # chunk directly used to leak an unserializable protobuf
                # object to the client, crashing the UI with "'str' object
                # has no attribute 'get'".

            # ── Phase 2.5: deterministic deliverable contract check ──────
            # .abi/specs/implemented/deterministic-deliverable-contract-verification.md
            # Reproduced live 2026-09-30: workflow.state reached COMPLETED
            # with zero real artifacts uploaded, and synthesis (free-text
            # LLM generation, below) fabricated a full "success" summary
            # instead of reporting it. Verify by code — never by trusting
            # the ephemeral's own "status": "completed" or asking an LLM to
            # judge — before synthesis is ever allowed to run.
            from steps import check_deliverable_contracts, transitive_dependents, build_workflow as _build_workflow

            current_nodes = build_result.get("nodes", {})
            current_tasks = tasks
            max_retries = 2
            retry_round = 0

            # With a reviewer, a missing deliverable is the reviewer's to
            # write; the deliverable check runs on its report (verify_run).
            while not reviewer_card and workflow.state == Status.COMPLETED:
                failed_ids = check_deliverable_contracts(current_tasks, current_nodes, results)
                if not failed_ids:
                    break

                retry_round += 1
                affected_ids = transitive_dependents(failed_ids, current_tasks)
                for fid in sorted(failed_ids):
                    # Deterministic, Orchestrator-generated text — never an
                    # LLM call. See the spec's point 2/3, confirmed with the
                    # user.
                    retry_note = f"{fid} no produjo el archivo esperado, reintentando con un nuevo agente..."
                    yield AgentResponse.status(
                        retry_note, agent=self.agent_name, context_id=context_id, task_id=task_id,
                        phase=RunPhase.EXECUTING.value, phase_detail=retry_note,
                    )

                if retry_round > max_retries:
                    # Stop. Don't fabricate anything, don't decide on the
                    # user's behalf — reuse the existing plan-confirmation
                    # flow (approve = retry same plan, reject = cancel,
                    # modify = different approach) instead of a parallel
                    # mechanism. Point 2, confirmed with the user.
                    failure_note = (
                        f"No se pudieron completar estas tareas tras {max_retries} intentos: "
                        f"{', '.join(sorted(affected_ids))}. ¿Querés reintentar el mismo plan, "
                        "o preferís un enfoque distinto?"
                    )
                    await self.record_pending_plan(context_id, plan, plan.get("objective", ""))
                    await self.update_session_context(
                        context_id, {"pending_plan_query": plan.get("objective", "")}
                    )
                    yield AgentResponse.status(failure_note, agent=self.agent_name,
                                                context_id=context_id, task_id=task_id,
                                                phase=RunPhase.EXECUTING.value,
                                                phase_detail=failure_note)
                    yield AgentResponse.input_required(failure_note)
                    return

                # Rebuild only the affected sub-plan — tasks that already
                # passed their contract keep their real artifacts, no need
                # to redo what genuinely worked.
                affected_tasks = [t for t in current_tasks if t.get("task_id") in affected_ids]
                reduced_plan = {**plan, "tasks": affected_tasks}
                yield AgentResponse.status(
                    "Preparing agents...", agent=self.agent_name,
                    context_id=context_id, task_id=task_id, phase=RunPhase.BUILDING.value,
                )
                rebuild_result = await _build_workflow({"plan": reduced_plan, "run_id": run_id}, context_id, task_id)
                if "error" in rebuild_result:
                    await self.record_error(context_id, "retry_error", rebuild_result["error"])
                    yield AgentResponse.error(rebuild_result["error"])
                    return

                workflow = rebuild_result["workflow"]
                current_nodes = {**current_nodes, **rebuild_result.get("nodes", {})}
                current_tasks = affected_tasks
                async for chunk in workflow.run_workflow():
                    results.append(chunk)
                    resp = A2AResponse.parse(chunk)
                    # Same status_message fallback as the main loop above —
                    # see its comment for why.
                    text = (resp.text or resp.status_message) if resp else None
                    if text:
                        yield AgentResponse.status(
                            text, agent=workflow.current_agent_name or self.agent_name,
                            context_id=context_id, task_id=task_id,
                            phase_detail=text, **_task_meta(current_tasks),
                        )

            # ── Phase 3: Synthesize results ──────────────────────
            if workflow.state == Status.COMPLETED:
                abi_logging(f"[✅] Workflow completed with {len(results)} results, "
                             f"{retry_round} retry round(s)")

                # Extract artifact URLs from agent responses
                from abi_core.common.artifact_store import generate_download_urls, format_artifact_links

                artifacts = []
                for r in results:
                    try:
                        resp = A2AResponse.parse(r)
                        if resp and resp.data:
                            for art in resp.data.get("uploaded_artifacts", []):
                                artifacts.append(art)
                    except Exception:
                        pass

                # One entry per filename, the latest upload. A Phase 2.5
                # retry, or a task that rewrote one of its input files, uploads
                # the same filename again — live 2026-10-06 the answer listed
                # game.py, player.py and assets.py twice each.
                from steps import merge_artifacts as _latest_per_file
                artifacts = _latest_per_file([], artifacts)

                integration = None
                missing_deliverables = []
                reviewer_report = None
                if reviewer_card:
                    # ── The run's reviewer (02.4) ─────────────────────
                    # The reviewer has the code agents' work; ask for its
                    # report, verify it (2.5 + 2.6 on the run's folder), send
                    # the findings back to the same reviewer for another round
                    # or confirm. The Orchestrator never repairs.
                    from steps import review_with_reviewer, run_artifacts

                    async for item in review_with_reviewer(
                        reviewer_card, plan, run_id, context_id, task_id,
                        self._run_with_heartbeat, self.agent_name,
                    ):
                        if isinstance(item, tuple):
                            integration, missing_deliverables, reviewer_report = item
                        else:
                            yield item

                    # The user's links: the run's final files.
                    artifacts = await run_artifacts(run_id) or artifacts
                    await generate_download_urls(artifacts)
                else:
                    await generate_download_urls(artifacts)
                    # ── Phase 2.6: integration review (report only) ───
                    # No reviewer (fewer than two .py files): the review still
                    # reports; nobody repairs. See steps.review_deliverables.
                    from steps import review_deliverables

                    async for item in self._run_with_heartbeat(
                        review_deliverables(artifacts, run_id), context_id, task_id,
                        "Verificando que los archivos funcionen juntos...",
                        phase=RunPhase.EXECUTING.value,
                    ):
                        if isinstance(item, _HeartbeatDone):
                            integration = item.value
                        else:
                            yield item

                # The model only describes the deliverable, in the user's
                # language. The verdict, the files and their links are added
                # below by code and never shown to it: reading the review, it
                # reported a set that ran without errors as "does not run"
                # and an untested one as "fully functional" (live
                # 2026-10-15). Spec: chainlit-delivery-result-card.md (C2).
                synthesis_query = config.build_synthesis_summary_prompt(
                    session_ctx.get("plan_user_message") or plan.get("objective", ""),
                    plan.get("objective", ""),
                    build_plan_view(plan)["steps"],
                )

                from abi_core.agent.llm_provider import invoke as llm_invoke

                async def _synthesize():
                    # call_timeout: see llm_provider.invoke()'s "Path A
                    # timeout" comment — this exact call hung indefinitely,
                    # reproduced twice live, right after a long ephemeral
                    # generation on the same Ollama instance. Raised from
                    # 300s to 2000s (2026-09-25) — reproduced live that a
                    # genuinely-progressing (not stuck) synthesis call missed
                    # 300s×2 by only 15s under concurrent load from multiple
                    # ephemeral agents sharing one Ollama instance; 300s was
                    # too tight for real contention, not just a stuck call.
                    # One retry with a fresh client before surfacing an error
                    # instead of hanging forever.
                    # The role prompt carries the synthesis rules (grounded,
                    # honest about failures, don't contradict the verified
                    # appendices). It used to reach only the tool-calling
                    # turn, never this call. Spec: persistent-agent-prompts.md.
                    return await llm_invoke(
                        config.LLM_CONFIG, synthesis_query, thread_id=context_id,
                        system_prompt=config.SYSTEM_PROMPT, call_timeout=2000,
                    )

                synthesis = None
                async for item in self._run_with_heartbeat(
                    _synthesize(), context_id, task_id, "Synthesizing results...",
                    phase=RunPhase.SYNTHESIZING.value,
                ):
                    if isinstance(item, _HeartbeatDone):
                        synthesis = item.value
                    else:
                        yield item

                final_response = synthesis or ""

                # The verdict is always code's: the full report when the set
                # failed or could not run (unverified is not a pass), and a
                # line saying exactly what was checked when it passed.
                integration_failed = bool(integration and integration.errors)
                integration_unverified = bool(
                    integration and not integration.errors
                    and getattr(integration, "execution_unverified", False)
                )
                if integration_failed or integration_unverified:
                    final_response += "\n\n" + integration.as_text()
                elif integration is not None:
                    final_response += "\n\n" + integration.as_pass_text()
                if missing_deliverables:
                    final_response += "\n\n❌ Entregables que no se produjeron: " + ", ".join(missing_deliverables)
                    integration_failed = True
                from steps import reviewer_note, handoff_errors
                note = reviewer_note(reviewer_report, await handoff_errors(run_id) if reviewer_card else None)
                if note:
                    final_response += "\n\n" + note
                # Links come from code too: the model no longer sees them.
                if artifacts:
                    final_response += format_artifact_links(artifacts)
                final_response = final_response.strip() or "Workflow completed successfully"
                outcome = (
                    "COMPLETED WITH INTEGRATION ERRORS" if integration_failed
                    else "COMPLETED, INTEGRATION UNVERIFIED" if integration_unverified
                    else "COMPLETED BY REVIEWER" if (reviewer_report or {}).get("missing_written")
                    else "SUCCESS"
                )

                # Fase 2D (ams-long-term-memory-no-consumer.md): write this
                # plan's outcome to long-term memory so a future planning
                # pass can recall it (Fase 2B). context_id=task_id, matching
                # the design as confirmed — open point, not resolved here:
                # whether this should key on task_id or the session's
                # context_id once identity-chain-hmac-contract's derivation
                # is in place (see that spec's Puntos débiles).
                objective = plan.get("objective", "")
                task_summaries = "; ".join(
                    f"{t.get('task_id', '?')}: {t.get('description', '')[:60]}"
                    for t in tasks
                )
                # AMS rejects any entity containing a comma (used as its own
                # storage delimiter) — reproduced live 2026-09-30: a normal
                # natural-language objective ("...movement, maze, ghosts...")
                # made every single Fase 2D write fail silently (logged as a
                # warning, never surfaced). `task` maps directly to
                # `entities`, so it must be comma-free; the real objective
                # text (with commas) still goes in `content`, unaffected.
                task_entity = objective[:50].replace(",", ";")
                await add_long_term_memory(
                    topic="plan_execution",
                    task=task_entity,
                    content=(
                        f"Plan '{objective}' with {len(tasks)} tasks: "
                        f"{outcome}. "
                        f"Tasks: {task_summaries}"
                    ),
                    context_id=task_id,
                )

                # QR of each artifact's download link, so the user can grab
                # it on their phone without retyping the URL — see
                # .abi/specs/agent-rich-elements.md.
                for art in artifacts:
                    url = art.get("download_url") or art.get("url")
                    if url:
                        yield AgentResponse.element(
                            "qr", {"data": url}, name=f"QR — {art.get('filename', 'download')}"
                        )

                # `query` here is the plan-confirmation sentinel
                # (__plan_confirm_approve__), not a meaningful user message
                # — record the plan's objective instead so conversation
                # history stays legible to future turns.
                await self.record_conversation_turn(
                    context_id, stored_plan.get("objective") or query, final_response,
                    window=config.CONVERSATION_WINDOW,
                )
                yield AgentResponse.text(final_response)

        except Exception as e:
            import traceback
            abi_logging(f"[❌] Error in orchestration: {e}\n{traceback.format_exc()}")
            await self.record_error(context_id, "exception", str(e))
            yield AgentResponse.error_from(e)
