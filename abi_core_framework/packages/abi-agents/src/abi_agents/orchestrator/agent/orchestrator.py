import asyncio
import json
from collections.abc import AsyncIterable

from abi_core.common import prompts
from abi_core.common.utils import abi_logging, format_plan_summary
from abi_core.common.workflow import Status
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent
from abi_core.agent.agent_response import AgentResponse
from abi_core.agent.plan_confirmation import (
    record_pending_plan as _shared_record_pending_plan,
    clear_pending_plan as _shared_clear_pending_plan,
)

from config import config


class AbiOrchestratorAgent(AbiAgent):
    """Orchestrator Agent — coordinates multi-agent workflows.

    Ephemeral agents self-deregister and self-destroy via self_deregister().
    The orchestrator is NOT responsible for ephemeral lifecycle.
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[tool_find_agent],
            system_prompt=prompts.ORCHESTRATOR_TOT_INSTRUCTIONS,
            content_types=['text', 'text/plain'],
        )

    async def _record_error(self, context_id: str, error_type: str, message: str):
        """Record an error in session context for next request awareness.

        State goes to the session backend (LB/multi-pod safe), never to
        per-process RAM. See WORKING_RULES → "Perspectiva Local vs Global".
        """
        await self.update_session_context(context_id, {f"last_error_{error_type}": message})
        abi_logging(f"[📝] Error recorded in session {context_id}: {error_type}")

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

    async def _record_pending_plan(self, context_id: str, plan: dict, original_query: str):
        """Record a plan awaiting the user's approve/reject/modify decision.

        The session-context bookkeeping is now shared (see
        abi_core.agent.plan_confirmation, extracted 2026-08-03 so a
        standalone agent can use the same primitive) — uses SessionStore
        (session_backend), not short-term/AMS memory, since this is
        genuinely per-session state (only this conversation cares about it).
        """
        await _shared_record_pending_plan(self.update_session_context, context_id, plan, original_query)

        # The methodology, though, is *system* context: it should be visible
        # to any agent that inspects this conversation, not just whichever
        # agent happens to receive the prompt directly (Local vs Global —
        # avoids the plan's methodology getting lost to context degradation
        # as it crosses agents). Best-effort, same as _record_pending_clarification.
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

    async def _clear_pending_plan(self, context_id: str):
        await _shared_clear_pending_plan(self.update_session_context, context_id)

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
            dag_result, heartbeats = await self._run_with_heartbeat(
                dag_coro, context_id, task_id, "Processing..."
            )
            for hb in heartbeats:
                yield hb

            if dag_result.get("failed_node"):
                error = dag_result.get("error", "Pipeline failed")
                abi_logging(f"[❌] DAG failed at {dag_result['failed_node']}: {error}")
                await self._record_error(context_id, "dag_failed", error)
                yield AgentResponse.error(error)
                return

            outputs = dag_result.get("node_outputs", {})

            # ── Check gate decision ──────────────────────────────
            gate = outputs.get("gate_decision", {})
            action = gate.get("action", "") if isinstance(gate, dict) else ""
            abi_logging(f"[🚦] Gate decision: action={action}, outputs_keys={list(outputs.keys())}")

            if action == "system_error":
                await self._record_error(context_id, "guardian_failed", gate.get("message", ""))
                yield AgentResponse.error(gate.get("message", "System error"))
                return

            if action == "blocked":
                await self._record_error(context_id, "blocked", gate.get("message", ""))
                yield AgentResponse.error(gate.get("message", "Request blocked"))
                return

            if action == "respond_direct":
                yield AgentResponse.status(
                    "Responding...", agent=self.agent_name,
                    context_id=context_id, task_id=task_id,
                )
                result_holder = {}

                async def _respond_direct():
                    inputs = {"messages": [{"role": "user", "content": query}]}
                    thread_config = {"configurable": {"thread_id": context_id}}
                    final = None
                    async for chunk in self.agent.astream(inputs, config=thread_config, stream_mode="updates"):
                        for _node, node_data in chunk.items():
                            if "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if hasattr(msg, 'content') and msg.content:
                                        final = msg.content
                    result_holder['response'] = final

                _, heartbeats = await self._run_with_heartbeat(
                    _respond_direct(), context_id, task_id, "Thinking..."
                )
                for hb in heartbeats:
                    yield hb

                yield AgentResponse.text(result_holder.get('response') or "No response generated")
                return

            # ── Plan confirmation replies (approve/reject/modify) ──
            if action == "plan_rejected":
                await self._clear_pending_plan(context_id)
                yield AgentResponse.text("Plan cancelado. Decime si querés que arme uno nuevo.")
                return

            if action == "plan_modify_requested":
                await self.update_session_context(context_id, {"awaiting_plan_modification": True})
                yield AgentResponse.input_required("¿Qué te gustaría cambiar del plan?")
                return

            if action == "execute_confirmed_plan":
                stored_plan = gate.get("plan")
                if not stored_plan:
                    yield AgentResponse.error(
                        "El plan pendiente ya no está disponible (la sesión pudo haber expirado). "
                        "Por favor volvé a describir tu solicitud."
                    )
                    return
                await self._clear_pending_plan(context_id)
                from steps import build_workflow
                build_result = await build_workflow({"plan": stored_plan}, context_id, task_id)

                if "gate_passthrough" in build_result:
                    yield AgentResponse.error(build_result["gate_passthrough"].get("message", "Unexpected gate passthrough"))
                    return
                if "error" in build_result:
                    await self._record_error(context_id, "plan_error", build_result["error"])
                    yield AgentResponse.error(build_result["error"])
                    return

            else:
                # ── action == "call_planner" — first time this plan appears ──
                plan_result = outputs.get("extract_plan", {})

                if "gate_passthrough" in plan_result:
                    yield AgentResponse.error(plan_result["gate_passthrough"].get("message", "Unexpected gate passthrough"))
                    return

                if "clarification" in plan_result:
                    abi_logging("[❓] Forwarding clarification request to user")
                    await self._record_pending_clarification(
                        context_id, query, plan_result["clarification"]
                    )
                    yield AgentResponse.input_required(
                        f"🤔 **Necesito mas informacion para crear el mejor plan:**\n\n{plan_result['clarification']}"
                    )
                    return

                if "error" in plan_result:
                    await self._record_error(context_id, "plan_error", plan_result["error"])
                    yield AgentResponse.error(plan_result["error"])
                    return

                plan = plan_result["plan"]
                model_status = outputs.get("check_model_availability", {}).get("model_status", {})
                summary = format_plan_summary(plan, model_status)
                await self._record_pending_plan(context_id, plan, query)
                yield AgentResponse.input_required(summary, action_type="plan_confirmation")
                return

            # ── Phase 2: Execute agent workflow ──────────────────
            workflow = build_result.get("workflow")
            plan = build_result.get("plan", {})

            if not workflow or workflow.is_empty():
                msg = "No agents could be assigned to execute the plan."
                await self._record_error(context_id, "empty_workflow", msg)
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

            results = []
            async for chunk in workflow.run_workflow():
                results.append(chunk)
                yield chunk

            # ── Phase 3: Synthesize results ──────────────────────
            if workflow.state == Status.COMPLETED:
                abi_logging(f"[✅] Workflow completed with {len(results)} results")

                # Extract artifact URLs from agent responses
                from abi_core.common.a2a_response import A2AResponse
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

                synthesis, heartbeats = await self._run_with_heartbeat(
                    _synthesize(), context_id, task_id, "Synthesizing results..."
                )
                for hb in heartbeats:
                    yield hb

                final_response = synthesis or "Workflow completed successfully"
                if artifacts and "download" not in final_response.lower():
                    final_response += format_artifact_links(artifacts)

                yield AgentResponse.text(final_response)

        except Exception as e:
            abi_logging(f"[❌] Error in orchestration: {e}")
            await self._record_error(context_id, "exception", str(e))
            yield AgentResponse.error(str(e))
