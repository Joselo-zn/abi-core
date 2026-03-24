"""
Planner Agent — decomposes queries into executable task plans.

The planning pipeline (analyze_query -> parse_plan -> assign_agents)
is registered as @agent.task() decorators in main.py and injected
as self.tool_graph by AbiCore.

This class provides the custom stream() with heartbeat support
and the Q&A clarification flow.
"""

import asyncio
import json
from collections.abc import AsyncIterable

from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_core.common.semantic_tools import tool_find_agent, tool_recommend_agents
from abi_core.agent.agent import AbiAgent, _HEARTBEAT_INTERVAL
from abi_core.agent.agent_response import AgentResponse

from config import config


class AbiPlannerAgent(AbiAgent):
    """Planner — divides queries into tasks and assigns agents.

    The decomposition pipeline is declared in main.py via @agent.task()
    decorators.  This class provides the custom stream() that:
    1. Calls the LLM to decompose the query
    2. Runs the DAG (parse + assign agents)
    3. Handles clarification / error / success branching
    4. Sends heartbeats during long-running phases
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[tool_find_agent, tool_recommend_agents],
            system_prompt=prompts.PLANNER_COT_INSTRUCTIONS,
            content_types=['text', 'text/plain'],
        )
        self.conversation_history = {}

    async def _run_with_heartbeat(self, coro, context_id, task_id, status_msg="Still working..."):
        """Run a coroutine with periodic heartbeat yields."""
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

    async def _call_llm(self, query, context):
        """Call the LLM to decompose the query. Returns raw text."""
        planning_query = f"User request: {query}\nContext: {json.dumps(context, indent=2)}"
        inputs = {"messages": [{"role": "user", "content": planning_query}]}

        final_response = None
        async for chunk in self.agent.astream(inputs, stream_mode="updates"):
            for _node, node_data in chunk.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, 'content') and msg.content:
                            final_response = msg.content
        return final_response

    async def stream(
        self, query: str, session_id: str, task_id: str
    ) -> AsyncIterable[dict[str, any]]:
        """Stream planning process with Q&A and heartbeat support."""

        abi_logging(f'[*] Planner stream - session: {session_id}, task: {task_id}')
        abi_logging(f'[📝] Query: {query}')

        try:
            # Build context from conversation history
            context = self.conversation_history.get(session_id, {})

            # Check if this is an answer to a previous question
            if session_id in self.conversation_history and ':' in query:
                parts = query.split(':', 1)
                answer_id = parts[0].strip()
                answer_text = parts[1].strip()
                context[answer_id] = answer_text
                self.conversation_history[session_id] = context
                abi_logging(f'[💬] Received answer for {answer_id}')

            # ── Phase 1: LLM decomposition (with heartbeat) ─────
            yield AgentResponse.status(
                "Analyzing query...",
                agent=self.agent_name,
                context_id=session_id,
                task_id=task_id,
            )

            llm_response, heartbeats = await self._run_with_heartbeat(
                self._call_llm(query, context),
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
                    error = dag_result.get("error", "Pipeline failed")
                    yield AgentResponse.error(error)
                    return

                outputs = dag_result.get("node_outputs", {})
                plan_data = outputs.get("assign_agents", {})
            else:
                # Fallback: no DAG, parse inline
                plan_data = self._parse_inline(llm_response)

            # ── Phase 3: Handle result ──────────────────────────
            status = plan_data.get("status", "error")

            if status == "needs_clarification":
                yield from self._yield_clarification(plan_data)

            elif status == "ready":
                plan = plan_data.get("plan", {})
                abi_logging(f"[✅] Plan ready with {len(plan.get('tasks', []))} tasks")

                yield AgentResponse(
                    content=self._format_plan_summary(plan),
                    response_type='text',
                    is_task_completed=False,
                )

                yield AgentResponse.success(
                    plan,
                    status='ready',
                    task_count=len(plan.get('tasks', [])),
                    execution_strategy=plan.get('execution_strategy', 'sequential'),
                )
            else:
                yield AgentResponse.error(
                    plan_data.get("message", "Unknown planning error")
                )

        except Exception as e:
            abi_logging(f"[❌] Error in planner: {e}")
            yield AgentResponse.error(str(e))

    # ── Helpers ─────────────────────────────────────────────────

    def _parse_inline(self, raw_response):
        """Fallback parser when no tool_graph is available."""
        cleaned = raw_response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip().replace('{{', '{').replace('}}', '}')

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "status": "ready",
                "plan": {
                    "objective": "Complete user request",
                    "tasks": [{
                        "task_id": "task_1",
                        "description": raw_response,
                        "agents": [], "agent_count": 1,
                        "dependencies": [],
                    }],
                    "execution_strategy": "sequential",
                },
            }

    def _yield_clarification(self, plan_data):
        """Format and yield clarification questions."""
        questions = plan_data.get("questions", [])
        partial = plan_data.get("partial_understanding", "")

        abi_logging(f"[❓] Need clarification: {len(questions)} questions")

        text = "I need some clarification to create the best plan:\n\n"
        text += f"What I understand so far: {partial}\n\n"
        text += "Questions:\n"

        for i, q in enumerate(questions, 1):
            q_id = q.get("id", f"q{i}")
            q_text = q.get("question", "")
            q_type = q.get("type", "required")
            options = q.get("options", [])

            text += f"{i}. [{q_type.upper()}] {q_text}\n"
            if options:
                text += f"   Options: {', '.join(options)}\n"
            text += f"   (Answer with: {q_id}: your answer)\n\n"

        yield AgentResponse.input_required(
            text, status='needs_clarification', questions=questions,
        )

    def _format_plan_summary(self, plan):
        """Format plan into human-readable summary."""
        objective = plan.get("objective", "Complete user request")
        tasks = plan.get("tasks", [])
        strategy = plan.get("execution_strategy", "sequential")

        lines = [
            f"📋 **Plan Created**\n",
            f"🎯 **Objective:** {objective}\n",
            f"📊 **Strategy:** {strategy.capitalize()}\n",
            f"**Tasks ({len(tasks)}):**\n",
        ]

        for i, t in enumerate(tasks, 1):
            tid = t.get("task_id", f"task_{i}")
            desc = t.get("description", "")
            agents = t.get("agents", [])
            deps = t.get("dependencies", [])

            lines.append(f"\n{i}. **{tid}:** {desc}")
            if agents and agents[0]:
                names = [a.get("name", "Unknown") for a in agents if a]
                lines.append(f"   👤 Agent(s): {', '.join(names)}")
            else:
                lines.append("   ⚠️ No agent assigned")
            if deps:
                lines.append(f"   🔗 Depends on: {', '.join(deps)}")

        lines.append("\n✅ Plan ready for execution by Orchestrator")
        return "\n".join(lines)

    def clear_session(self, session_id):
        """Clear conversation history for a session."""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
            abi_logging(f"[🗑️] Cleared session {session_id}")
