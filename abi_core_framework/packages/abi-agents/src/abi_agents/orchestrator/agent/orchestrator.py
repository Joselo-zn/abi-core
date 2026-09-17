import asyncio
import json
from collections.abc import AsyncIterable

from abi_core.common import prompts
from abi_core.common.utils import abi_logging, format_plan_summary
from abi_core.common.workflow import Status
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent, _HeartbeatDone
from abi_core.agent.agent_response import AgentResponse
from abi_core.agent.routing_tools import build_routing_decision_schema, format_system_state
from abi_core.memory import MEMORY_TOOLS

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
            system_prompt=prompts.ORCHESTRATOR_TOT_INSTRUCTIONS,
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
        prompt = f"{system_state}\n\nUser message: {query!r}" if system_state else f"User message: {query!r}"
        if gathered_context:
            prompt += f"\n\nContext you already gathered this turn: {gathered_context}"

        # This call has NO system prompt otherwise (decision_llm is the bare
        # model, not self.agent — ORCHESTRATOR_TOT_INSTRUCTIONS never reaches
        # it). Experiment (2026-09-15, see
        # .abi/specs/orchestrator-conversation-memory.md): with zero framing,
        # the model was observed pattern-matching only the literal current
        # message into `objective`, ignoring a correctly-injected
        # [SYSTEM STATE] Recent conversation block sitting right above it in
        # the same prompt — verified by reconstructing the exact prompt by
        # hand and comparing it to `decision.objective` in the logs. Only
        # added when there's an actual system_state block to point at.
        messages = prompt
        if system_state:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=(
                    "Before answering, read the full prompt carefully, "
                    "including the [SYSTEM STATE] block, and use anything "
                    "relevant from it — do not just pattern-match the "
                    "current message in isolation.\n\n"
                    "This matters most for `objective` (action=create_plan): "
                    "a downstream planner will see ONLY the text you write "
                    "into `objective` — nothing else from this conversation, "
                    "no [SYSTEM STATE] block, nothing. If you copy the "
                    "current message verbatim and it omits a detail already "
                    "given in [SYSTEM STATE] Recent conversation (place, "
                    "dates, constraints, etc.), the planner has no way to "
                    "know it and will ask the user to repeat information "
                    "they already gave. Merge the relevant detail into "
                    "`objective` yourself first — do not leave that "
                    "merging for later."
                )),
                HumanMessage(content=prompt),
            ]

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
        )
        planner_results = None
        async for item in self._run_with_heartbeat(
            call_planner(query, context_id, task_id), context_id, task_id, "Planning...",
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
        yield AgentResponse.input_required(summary, action_type="plan_confirmation")

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
            )

            session_ctx = await self.get_session_context(context_id)
            dag_coro = self.tool_graph.execute({
                "query": query,
                "context_id": context_id,
                "task_id": task_id,
                "session_context": session_ctx,
            })
            dag_result = None
            async for item in self._run_with_heartbeat(dag_coro, context_id, task_id, "Processing..."):
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
                    context_id, task_id, "Thinking...",
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

                if decision.action == "create_plan":
                    async for r in self._call_planner_and_respond(decision.objective or query, context_id, task_id):
                        yield r
                    return

                if decision.action == "resolve_pending_clarification":
                    await self._clear_pending_clarification(context_id)
                    original = pending_clarification.get("original_query", "")
                    answer = decision.answer or query
                    enriched = f"{original}\n\nUser clarification: {answer}" if original else answer
                    async for r in self._call_planner_and_respond(enriched, context_id, task_id):
                        yield r
                    return

                if decision.action == "resolve_pending_plan":
                    if decision.decision == "approve":
                        stored_plan = session_ctx.get("pending_plan")
                        run_confirmed_plan = True
                    elif decision.decision == "reject":
                        await self.clear_pending_plan(context_id)
                        yield AgentResponse.text("Plan cancelado. Decime si querés que arme uno nuevo.")
                        return
                    elif decision.decision == "modify":
                        feedback = decision.feedback
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

                if decision.action == "answer_directly":
                    answer_text = decision.text or "No pude interpretar tu respuesta. ¿Podés reformularla?"
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
                from steps import build_workflow
                build_result = await build_workflow({"plan": stored_plan}, context_id, task_id)

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

            results = []
            async for chunk in workflow.run_workflow():
                results.append(chunk)
                resp = A2AResponse.parse(chunk)
                if resp and resp.text:
                    yield AgentResponse.status(
                        resp.text, agent=workflow.current_agent_name or self.agent_name,
                        task_key=workflow.current_node_key, task_label=workflow.current_node_label,
                        context_id=context_id, task_id=task_id,
                    )
                # else: intermediate A2A protocol event with no user-facing
                # text (e.g. a raw StreamResponse) — skip it. Yielding the raw
                # chunk directly used to leak an unserializable protobuf
                # object to the client, crashing the UI with "'str' object
                # has no attribute 'get'".

            # ── Phase 3: Synthesize results ──────────────────────
            if workflow.state == Status.COMPLETED:
                abi_logging(f"[✅] Workflow completed with {len(results)} results")

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

                await generate_download_urls(artifacts)

                # Build synthesis prompt
                from abi_core.common.context_loader import build_execution_prompt

                artifacts_paths = [
                    f"{art.get('filename', '?')}: {art.get('download_url', art.get('url', ''))}"
                    for art in artifacts
                ]

                synthesis_query = (
                    f"Synthesize the following workflow results:\n"
                    f"Plan: {json.dumps(plan, indent=2)}\n"
                    f"Results count: {len(results)}\n"
                )
                if artifacts_paths:
                    synthesis_query += "Generated artifacts:\n" + "\n".join(f"  - {p}" for p in artifacts_paths) + "\n"
                synthesis_query += "Include download links for any generated files in your response."

                from abi_core.agent.llm_provider import invoke as llm_invoke

                async def _synthesize():
                    return await llm_invoke(
                        config.LLM_CONFIG, synthesis_query, thread_id=context_id,
                    )

                synthesis = None
                async for item in self._run_with_heartbeat(
                    _synthesize(), context_id, task_id, "Synthesizing results...",
                ):
                    if isinstance(item, _HeartbeatDone):
                        synthesis = item.value
                    else:
                        yield item

                final_response = synthesis or "Workflow completed successfully"
                if artifacts and "download" not in final_response.lower():
                    final_response += format_artifact_links(artifacts)

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
            yield AgentResponse.error(str(e))
