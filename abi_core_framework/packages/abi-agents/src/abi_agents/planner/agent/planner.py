"""
Planner Agent — decomposes queries into executable task plans.

The planning pipeline (analyze_query -> parse_plan -> assign_agents)
is registered as @agent.step() decorators in main.py and injected
as self.tool_graph by AbiCore.
"""

import json
import os
from collections.abc import AsyncIterable

from abi_core.common.utils import abi_logging, clean_llm_json, format_plan_summary
from abi_core.agent.agent import AbiAgent, _HeartbeatDone
from abi_core.agent.agent_response import AgentResponse

from config import config

# Fixed whitelist of tools a `direct_tool` task may invoke — checked here in
# code, never left to the LLM's judgment (the LLM only ever picks a name
# that must ALSO pass PlanTask.direct_tool's Pydantic Literal at planning
# time; this is the second, execution-time gate). See
# .abi/specs/planner-direct-tool-pdf.md.
def _direct_tool_whitelist() -> dict:
    from abi_core.common.library_tools import write_pdf

    return {"write_pdf": write_pdf}


class AbiPlannerAgent(AbiAgent):
    """Planner — divides queries into tasks and assigns agents.

    Pipeline declared in main.py via @agent.step().
    Custom stream() handles LLM call, DAG execution, and branching.
    Heartbeat via inherited _run_with_heartbeat().
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[],  # Planner only decomposes — no tool calls during LLM phase
            system_prompt=config.SYSTEM_PROMPT,
            content_types=['text', 'text/plain'],
        )

    async def _call_llm(self, query, context, session_id):
        """Call the LLM to decompose the query. Returns a validated
        PlannerOutput, not raw text.

        No tools — the planner only reasons. Tool resolution is handled by
        assign_agents (find_agent) and the builder.

        Uses `invoke_structured` (schema-constrained decoding via
        `with_structured_output`), not plain-text `invoke()` — a
        prompt-only "respond in JSON" instruction turned out to be
        model-dependent (devstral:24b ignored it outright, answering in
        plain prose; see invoke_structured()'s own docstring for the full
        story). Forcing the schema means this no longer depends on a given
        model choosing to comply.
        """
        from abi_core.agent.llm_provider import invoke_structured
        from abi_core.common.plan_models import PlannerOutput

        planning_query = config.build_planning_query(query, context)
        result = await invoke_structured(
            config.LLM_CONFIG,
            planning_query,
            schema=PlannerOutput,
            thread_id=session_id,
            system_prompt=config.SYSTEM_PROMPT,
        )

        # `Plan.methodology`/`methodology_rationale` are still real schema
        # fields (PlannerOutput -> Plan) — the model fills them in on its
        # own initiative even with no explicit instruction to, because the
        # field's own description ("Decomposition methodology applied")
        # reads as a request for one. Verified live: with select_methodology
        # removed, the model started citing "Polya" from its own general
        # knowledge instead — an unprompted, ungoverned choice, not this
        # framework's. The methodology is no longer a per-request decision
        # (that was the whole point of replacing it with the fixed Agile
        # persona above) — overwrite deterministically instead of trusting
        # the model to self-report the framing we already gave it.
        if result.status == "ready" and result.plan:
            result.plan.methodology = "Agile (Scrum/Kanban)"
            result.plan.methodology_rationale = (
                "Fixed framing for every plan — see PLANNER_COT_INSTRUCTIONS: "
                "the Planner acts as a Technical Lead breaking the request "
                "into a prioritized backlog of User Stories, not a "
                "per-request methodology choice."
            )
        return result

    async def _execute_direct_tool(
        self, payload: dict, session_id: str, task_id: str
    ) -> AsyncIterable[dict[str, any]]:
        """Deterministic execution of a `direct_tool` task (e.g. write_pdf).

        No planning DAG, no agentic tool-calling — the tool to call is
        resolved against a fixed whitelist in code, never chosen by the
        LLM. The LLM's only job here is generating the artifact's text
        content from the task description (plain completion, no tools).
        See .abi/specs/planner-direct-tool-pdf.md.
        """
        from abi_core.agent.llm_provider import invoke
        from abi_core.common.artifact_store import upload_workspace_artifacts
        from abi_core.common.library_tools import WORKSPACE

        tool_name = payload.get("_direct_tool")
        description = payload.get("description", "")
        target_tag = payload.get("target_tag") or "output.pdf"

        whitelist = _direct_tool_whitelist()
        tool_fn = whitelist.get(tool_name)
        if tool_fn is None:
            yield AgentResponse.error(f"direct_tool '{tool_name}' is not in the whitelist")
            return

        yield AgentResponse.status(
            f"Generating {target_tag}...",
            agent=self.agent_name,
            context_id=session_id,
            task_id=task_id,
        )

        try:
            # Wrapped in the same heartbeat mechanism stream()'s Phase 1 uses
            # for _call_llm — without it, a slow content generation (a large
            # deliverable on a CPU-bound local model) runs with no status
            # pings at all, silently outliving the UI/orchestrator's patience
            # while the LLM call itself keeps running server-side with
            # nothing to show for it. See .abi/specs/direct-tool-fixes.md.
            content = None
            async for item in self._run_with_heartbeat(
                invoke(
                    config.LLM_CONFIG,
                    config.build_direct_tool_content_prompt(description),
                    thread_id=session_id,
                ),
                session_id, task_id, f"Generating {target_tag}...",
            ):
                if isinstance(item, _HeartbeatDone):
                    content = item.value
                else:
                    yield item

            result = tool_fn.func(filename=target_tag, content=content)
            abi_logging(f"[⚡] direct_tool '{tool_name}': {result}")

            # The Planner is long-lived (not ephemeral like a zombie), so its
            # workspace is never wiped between requests — scanning it wholesale
            # would re-upload/re-report leftover files from earlier direct_tool
            # calls. Upload only the file this call just produced, then remove
            # it so the workspace is clean for the next call.
            exclude_paths = [
                os.path.join(WORKSPACE, f)
                for f in os.listdir(WORKSPACE)
                if f != target_tag
            ] if os.path.isdir(WORKSPACE) else []

            uploaded_artifacts = await upload_workspace_artifacts(
                agent_name=config.AGENT_NAME,
                workspace=WORKSPACE,
                exclude=exclude_paths,
            )

            try:
                os.remove(os.path.join(WORKSPACE, target_tag))
            except OSError:
                pass

            yield AgentResponse.result({
                "status": "completed",
                "result": result,
                "uploaded_artifacts": uploaded_artifacts,
                "agent": config.AGENT_NAME,
            })
        except Exception as e:
            abi_logging(f"[❌] direct_tool '{tool_name}' failed: {e}")
            yield AgentResponse.error(f"direct_tool '{tool_name}' failed: {e}")

    async def stream(
        self, query: str, session_id: str, task_id: str
    ) -> AsyncIterable[dict[str, any]]:
        """Stream planning process with Q&A and heartbeat support."""

        abi_logging(f'[*] Planner stream - session: {session_id}, task: {task_id}')
        abi_logging(f'[📝] Query: {query}')

        # Deterministic short-circuit: a direct_tool task sent by
        # build_workflow (orchestrator/agent/steps.py) arrives as structured
        # JSON with a `_direct_tool` marker, never as prose — same
        # "sentinel, not LLM classification" pattern as plan-confirmation
        # and clarification-answer routing. Checked BEFORE the planning DAG
        # runs, so a direct_tool task never goes through another round of
        # LLM planning. See .abi/specs/planner-direct-tool-pdf.md.
        try:
            parsed_query = json.loads(query)
        except (json.JSONDecodeError, TypeError):
            parsed_query = None

        if isinstance(parsed_query, dict) and "_direct_tool" in parsed_query:
            async for item in self._execute_direct_tool(parsed_query, session_id, task_id):
                yield item
            return

        try:
            # Session context managed by AbiAgent base
            context, _ = await self.process_answer(session_id, query)

            # Phase 0 (dynamic per-request methodology selection — Polya/WBS/
            # SMART/etc., via methodology_tools.select_methodology) removed:
            # the fixed Agile Tech Lead persona now baked directly into
            # PLANNER_COT_INSTRUCTIONS replaces it — one system prompt, no
            # extra LLM call before decomposition even starts (that call
            # alone cost minutes on local models). Also sidesteps a real
            # failure mode found live: devstral:24b, fine-tuned with its own
            # "OpenHands" agentic persona baked into its Modelfile, answered
            # PLANNER_COT_INSTRUCTIONS' plain "decompose into tasks"
            # framing with "I don't have the tools needed" — refusing to
            # plan because IT personally has no tools (Planner intentionally
            # gives it none — see class docstring). Reframing the role as a
            # Tech Lead writing a backlog for OTHER developers to build
            # doesn't imply the model itself needs tools, so it stops
            # triggering that refusal pattern.

            # ── Phase 1: LLM decomposition (with heartbeat) ─────
            yield AgentResponse.status(
                "Analyzing query...",
                agent=self.agent_name,
                context_id=session_id,
                task_id=task_id,
            )

            llm_response = None
            async for item in self._run_with_heartbeat(
                self._call_llm(query, context, session_id),
                session_id, task_id, "Analyzing query...",
            ):
                if isinstance(item, _HeartbeatDone):
                    llm_response = item.value
                else:
                    yield item

            if not llm_response:
                yield AgentResponse.error("Empty response from LLM")
                return

            # ── Phase 2: Parse + assign agents via DAG (with heartbeat) ──
            if self.tool_graph is not None:
                yield AgentResponse.status(
                    "Building plan...",
                    agent=self.agent_name,
                    context_id=session_id,
                    task_id=task_id,
                )

                dag_coro = self.tool_graph.execute({
                    "query": query,
                    "context": context,
                    "llm_response": llm_response,
                })
                dag_result = None
                async for item in self._run_with_heartbeat(dag_coro, session_id, task_id, "Assigning agents..."):
                    if isinstance(item, _HeartbeatDone):
                        dag_result = item.value
                    else:
                        yield item

                if dag_result.get("failed_node"):
                    yield AgentResponse.error(dag_result.get("error", "Pipeline failed"))
                    return

                outputs = dag_result.get("node_outputs", {})
                plan_data = outputs.get("assign_agents", {})
            else:
                plan_data = clean_llm_json(llm_response)

            # ── Phase 3: Handle result ──────────────────────────
            status = plan_data.get("status", "error")

            if status == "needs_clarification":
                async for task in self._yield_clarification(plan_data):
                    yield task

            elif status == "ready":
                # methodology/methodology_rationale are already set
                # deterministically in _call_llm (Agile Tech Lead framing,
                # not a per-request model choice) — this branch used to
                # re-set them from a `methodology_result` that no longer
                # exists since Phase 0's select_methodology call was
                # removed, crashing every successful plan with a NameError.
                plan = plan_data.get("plan", {})
                abi_logging(f"[✅] Plan ready with {len(plan.get('tasks', []))} tasks")

                yield AgentResponse.status(format_plan_summary(plan))
                yield AgentResponse.result(plan)
            else:
                yield AgentResponse.error(plan_data.get("message", "Unknown planning error"))

        except Exception as e:
            abi_logging(f"[❌] Error in planner: {e}")
            yield AgentResponse.error(str(e))
