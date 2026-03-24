import asyncio
import json
from collections.abc import AsyncIterable

from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_core.common.workflow import Status
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent, _HEARTBEAT_INTERVAL
from abi_core.agent.agent_response import AgentResponse

from config import config


class AbiOrchestratorAgent(AbiAgent):
    """Orchestrator Agent — coordinates multi-agent workflows.

    The planning pipeline (call_planner -> extract_plan -> build_workflow)
    is registered as @agent.task() decorators in main.py and injected
    as self.tool_graph by AbiCore.

    This class provides a custom stream() that executes the DAG,
    handles branching (clarification, errors), and synthesizes results.
    Heartbeat keepalives are sent during long-running phases (DAG
    execution and synthesis) to prevent proxy timeouts.
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[tool_find_agent],
            system_prompt=prompts.ORCHESTRATOR_COT_INSTRUCTIONS,
            content_types=['text', 'text/plain'],
        )

    async def _run_with_heartbeat(self, coro, context_id, task_id, status_msg="Still working..."):
        """Run a coroutine with periodic heartbeat yields.

        Returns (result, heartbeats) where heartbeats is a list of
        AgentResponse.status() that should be yielded by the caller.
        """
        heartbeats = []
        task = asyncio.create_task(coro)

        while not task.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(task), timeout=_HEARTBEAT_INTERVAL
                )
            except asyncio.TimeoutError:
                if not task.done():
                    heartbeats.append(AgentResponse.status(
                        status_msg,
                        agent=self.agent_name,
                        context_id=context_id,
                        task_id=task_id,
                    ))

        return task.result(), heartbeats

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

            # ── Phase 1: Planning pipeline (with heartbeat) ─────
            yield AgentResponse.status(
                "Planning...",
                agent=self.agent_name,
                context_id=context_id,
                task_id=task_id,
            )

            dag_coro = self.tool_graph.execute({
                "query": query,
                "context_id": context_id,
                "task_id": task_id,
            })
            dag_result, heartbeats = await self._run_with_heartbeat(
                dag_coro, context_id, task_id, "Planning in progress..."
            )
            for hb in heartbeats:
                yield hb

            # Check for DAG failure
            if dag_result.get("failed_node"):
                error = dag_result.get("error", "Pipeline failed")
                abi_logging(f"[❌] DAG failed at {dag_result['failed_node']}: {error}")
                yield AgentResponse.error(error)
                return

            # Get build_workflow output
            outputs = dag_result.get("node_outputs", {})
            build_result = outputs.get("build_workflow", {})

            # Handle clarification
            if "clarification" in build_result:
                abi_logging("[❓] Forwarding clarification request to user")
                formatted = (
                    "🤔 **Necesito mas informacion para crear el mejor plan:**"
                    f"\n\n{build_result['clarification']}"
                )
                yield AgentResponse.input_required(formatted)
                return

            # Handle extraction error
            if "error" in build_result:
                yield AgentResponse.error(build_result["error"])
                return

            # ── Phase 2: Execute agent workflow (yields keep SSE alive) ──
            workflow = build_result["workflow"]
            plan = build_result["plan"]

            abi_logging(f"[📋] Executing plan with {len(plan.get('tasks', []))} tasks")

            results = []
            async for chunk in workflow.run_workflow():
                results.append(chunk)
                yield chunk

            # ── Phase 3: Synthesize results (with heartbeat) ────
            if workflow.state == Status.COMPLETED:
                abi_logging(f"[✅] Workflow completed with {len(results)} results")

                synthesis_query = (
                    f"Synthesize the following workflow results:\n"
                    f"Plan: {json.dumps(plan, indent=2)}\n"
                    f"Results count: {len(results)}"
                )

                result_holder = {}

                async def _synthesize():
                    inputs = {"messages": [{"role": "user", "content": synthesis_query}]}
                    final = None
                    async for chunk in self.agent.astream(inputs, stream_mode="updates"):
                        for _node, node_data in chunk.items():
                            if "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if hasattr(msg, 'content') and msg.content:
                                        final = msg.content
                    result_holder['synthesis'] = final

                synth_coro = _synthesize()
                _, heartbeats = await self._run_with_heartbeat(
                    synth_coro, context_id, task_id, "Synthesizing results..."
                )
                for hb in heartbeats:
                    yield hb

                yield AgentResponse.success(
                    result_holder.get('synthesis') or "Workflow completed successfully"
                )

        except Exception as e:
            abi_logging(f"[❌] Error in orchestration: {e}")
            yield AgentResponse.error(str(e))
