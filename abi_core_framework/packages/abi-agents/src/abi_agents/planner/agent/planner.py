"""
Planner Agent — decomposes queries into executable task plans.

The planning pipeline (analyze_query -> parse_plan -> assign_agents)
is registered as @agent.step() decorators in main.py and injected
as self.tool_graph by AbiCore.
"""

import json
from collections.abc import AsyncIterable

from abi_core.common import prompts
from abi_core.common.utils import abi_logging, clean_llm_json, format_plan_summary
from abi_core.agent.agent import AbiAgent
from abi_core.agent.agent_response import AgentResponse

from config import config


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
            system_prompt=prompts.PLANNER_COT_INSTRUCTIONS,
            content_types=['text', 'text/plain'],
        )

    async def _call_llm(self, query, context, session_id):
        """Call the LLM to decompose the query. Returns raw text.
        
        No tools — the planner only reasons and produces structured JSON.
        Tool resolution is handled by assign_agents (find_agent) and the builder.
        """
        from abi_core.agent.llm_provider import invoke

        planning_query = f"User request: {query}\nContext: {json.dumps(context, indent=2)}"
        return await invoke(
            config.LLM_CONFIG,
            planning_query,
            thread_id=session_id,
            system_prompt=prompts.PLANNER_COT_INSTRUCTIONS,
        )

    async def stream(
        self, query: str, session_id: str, task_id: str
    ) -> AsyncIterable[dict[str, any]]:
        """Stream planning process with Q&A and heartbeat support."""

        abi_logging(f'[*] Planner stream - session: {session_id}, task: {task_id}')
        abi_logging(f'[📝] Query: {query}')

        try:
            # Session context managed by AbiAgent base
            context, _ = await self.process_answer(session_id, query)

            # ── Phase 1: LLM decomposition (with heartbeat) ─────
            yield AgentResponse.status(
                "Analyzing query...",
                agent=self.agent_name,
                context_id=session_id,
                task_id=task_id,
            )

            llm_response, heartbeats = await self._run_with_heartbeat(
                self._call_llm(query, context, session_id),
                session_id, task_id, "Analyzing query..."
            )
            for hb in heartbeats:
                yield hb

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
                dag_result, heartbeats = await self._run_with_heartbeat(
                    dag_coro, session_id, task_id, "Assigning agents..."
                )
                for hb in heartbeats:
                    yield hb

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
                plan = plan_data.get("plan", {})
                abi_logging(f"[✅] Plan ready with {len(plan.get('tasks', []))} tasks")

                yield AgentResponse.status(format_plan_summary(plan))
                yield AgentResponse.result(plan)
            else:
                yield AgentResponse.error(plan_data.get("message", "Unknown planning error"))

        except Exception as e:
            abi_logging(f"[❌] Error in planner: {e}")
            yield AgentResponse.error(str(e))
