"""
Base ABI Agent Class
Core agent functionality for ABI Framework
"""

import asyncio
from typing import Any, Dict, List, AsyncIterable, Optional

from abi_core.common.utils import abi_logging
from abi_core.agent.llm_provider import create_llm
from abi_core.agent.agent_response import AgentResponse

# Heartbeat interval in seconds — must be under proxy timeout (CloudFront = 30s)
_HEARTBEAT_INTERVAL = 15


class AbiAgent:
    """Base class for all ABI agents.

    Handles LLM creation, LangChain agent wiring, and a default
    ``stream()`` implementation so subclasses only need to pass
    configuration.  Override ``stream()`` for custom behaviour.

    The optional ``tool_graph`` attribute is injected by ``AbiCore``
    when tasks/tools are registered via ``@app.task()`` / ``@app.tool()``
    decorators.  Subclasses can use ``self.tool_graph`` to execute
    deterministic DAG pipelines.

    Args:
        agent_name: Identifier for this agent.
        description: Human-readable description.
        llm_config: Dict consumed by ``create_llm()`` (provider, model, etc.).
        tools: List of LangChain-compatible tools for the agent.
        system_prompt: System prompt / instructions for the agent.
        content_types: Accepted content types (default: text/plain).
    """

    def __init__(
        self,
        agent_name: str,
        description: str,
        llm_config: Dict[str, Any],
        tools: List = None,
        system_prompt: str = "",
        content_types: List[str] = None,
    ):
        self.agent_name = agent_name
        self.description = description
        self.llm_config = llm_config
        self.content_types = content_types or ["text", "text/plain"]

        # Injected by AbiCore when @app.task()/@app.tool() are used
        self.tool_graph = None  # Optional[ToolExecutionGraph]
        self.extra_tools: List = []  # LangChain tools from @app.tool()

        # Create LLM via unified provider
        self.llm = create_llm(llm_config)

        # Merge explicit tools with any injected by AbiCore later
        self._base_tools = tools or []

        # Checkpointer for conversation memory (MemorySaver — in-process)
        from langgraph.checkpoint.memory import MemorySaver

        self.checkpointer = MemorySaver()

        # Create LangChain agent with tools + checkpointer
        from langchain.agents import create_agent

        self.agent = create_agent(
            model=self.llm,
            tools=self._base_tools,
            system_prompt=system_prompt,
            checkpointer=self.checkpointer,
        )

        abi_logging(f"[🚀] {agent_name} agent ready")

    # ── Session management ──────────────────────────────────────

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Return accumulated context for a session."""
        if not hasattr(self, '_conversation_history'):
            self._conversation_history = {}
        return self._conversation_history.get(session_id, {})

    def process_answer(self, session_id: str, query: str) -> tuple:
        """Detect if query is an answer (``id: text``), update context.

        Returns:
            ``(context, was_answer)`` — the session context dict and
            whether the query was parsed as an answer.
        """
        if not hasattr(self, '_conversation_history'):
            self._conversation_history = {}

        context = self._conversation_history.get(session_id, {})

        if session_id in self._conversation_history and ':' in query:
            parts = query.split(':', 1)
            answer_id = parts[0].strip()
            answer_text = parts[1].strip()
            context[answer_id] = answer_text
            self._conversation_history[session_id] = context
            abi_logging(f'[💬] Received answer for {answer_id}')
            return context, True

        # Ensure session exists even if not an answer
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = context

        return context, False

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if not hasattr(self, '_conversation_history'):
            self._conversation_history = {}
            return
        if session_id in self._conversation_history:
            del self._conversation_history[session_id]
            abi_logging(f"[🗑️] Cleared session {session_id}")

    async def _yield_clarification(self, plan_data):
        """Format and yield clarification questions from a plan response.

        Parses ``plan_data`` with ``status: "needs_clarification"`` and
        yields an ``AgentResponse.input_required`` with formatted questions.
        Any agent that handles multi-turn clarification can use this.
        """
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

    def _resolve_task(self, task_id: str):
        """Resolve which registered task to execute for this request.

        Priority:
        1. Match by task_id if it corresponds to a registered task
        2. Convention: task named "route_to_task" or "main"
        3. Fallback to first registered task
        """
        # 1. Explicit task_id match
        for t in self._registered_tasks.values():
            if t.task_id == task_id:
                return t

        # 2. Convention-based entry points
        for name in ("route_to_task", "main"):
            if name in self._registered_tasks:
                return self._registered_tasks[name]

        # 3. Fallback
        return next(iter(self._registered_tasks.values()))

    async def _run_with_heartbeat(self, coro, context_id, task_id, status_msg="Still working..."):
        """Run a coroutine with periodic heartbeat yields.

        Executes *coro* in a background task and collects
        ``AgentResponse.status()`` heartbeats every ``_HEARTBEAT_INTERVAL``
        seconds.  Useful in custom ``stream()`` overrides where the
        base heartbeat loop is not available.

        Args:
            coro: Awaitable to execute.
            context_id: Context identifier for heartbeat metadata.
            task_id: Task identifier for heartbeat metadata.
            status_msg: Text shown in heartbeat status messages.

        Returns:
            ``(result, heartbeats)`` — the coroutine result and a list
            of ``AgentResponse`` heartbeats that the caller should yield.
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
    ) -> AsyncIterable[Dict[str, Any]]:
        """Process query and stream responses with keepalive heartbeats.

        If ``self.tool_graph`` is set (via @agent.step() decorators),
        executes the DAG deterministically. Otherwise falls back to
        the LLM agent.

        Override in subclasses for custom behaviour (e.g. Planner,
        Orchestrator).
        """
        import json as _json

        abi_logging(f'[📝] {self.agent_name} processing: {query}.')

        # Auto-manage session context
        context, was_answer = self.process_answer(context_id, query)

        yield AgentResponse.status(
            "Processing...",
            agent=self.agent_name,
            context_id=context_id,
            task_id=task_id,
        )

        # ── Path 0: registered tasks → execute task function ────
        if hasattr(self, '_registered_tasks') and self._registered_tasks:
            task_entry = self._resolve_task(task_id)
            abi_logging(f"[🎯] Executing task '{task_entry.name}' ({task_entry.task_id})")
            if task_entry.tools:
                abi_logging(f"[🔧] Task tool scope: {task_entry.tools}")
            try:
                import inspect

                task_fn = task_entry.fn
                if inspect.isasyncgenfunction(task_fn):
                    async for chunk in task_fn(query=query):
                        yield chunk
                elif inspect.iscoroutinefunction(task_fn):
                    result = await task_fn(query=query)
                    if isinstance(result, dict):
                        yield AgentResponse.result(result)
                    else:
                        yield AgentResponse.text(str(result))
                return
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                abi_logging(f"[❌] Task '{task_entry.name}' failed: {e}\n{tb}", level="error")
                yield AgentResponse.error(str(e))
                return

        # ── Path A: tool_graph exists → execute DAG ─────────────
        if self.tool_graph is not None:
            try:
                # Parse query as JSON for structured input, fallback to {"query": query}
                try:
                    input_data = _json.loads(query) if isinstance(query, str) else query
                    if not isinstance(input_data, dict):
                        input_data = {"query": query}
                except (_json.JSONDecodeError, TypeError):
                    input_data = {"query": query}

                # Always include context_id and task_id
                input_data.setdefault("context_id", context_id)
                input_data.setdefault("task_id", task_id)

                dag_coro = self.tool_graph.execute(input_data)
                dag_result, heartbeats = await self._run_with_heartbeat(
                    dag_coro, context_id, task_id, "Executing pipeline..."
                )
                for hb in heartbeats:
                    yield hb

                if dag_result.get("failed_node"):
                    yield AgentResponse.error(
                        dag_result.get("error", "Pipeline failed"),
                        agent=self.agent_name,
                    )
                    return

                # Return the last node's output as the result
                outputs = dag_result.get("node_outputs", {})
                completed = dag_result.get("completed_nodes", [])
                last_output = outputs.get(completed[-1]) if completed else None

                if last_output is not None:
                    yield AgentResponse.result(last_output)
                else:
                    yield AgentResponse.text("Completed")
                return

            except Exception as e:
                abi_logging(f'[❌] Error in {self.agent_name} DAG: {e}', level='error')
                yield AgentResponse.error(str(e))
                return

        # ── Path B: no tool_graph → use LLM agent ──────────────
        result_holder: Dict[str, Any] = {}

        async def _run_llm():
            inputs = {"messages": [{"role": "user", "content": query}]}
            thread_config = {"configurable": {"thread_id": context_id}}
            final_response = None
            async for chunk in self.agent.astream(
                inputs, config=thread_config, stream_mode="updates"
            ):
                for _node_name, node_data in chunk.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            if hasattr(msg, 'content') and msg.content:
                                final_response = msg.content
            result_holder['response'] = final_response

        llm_task = asyncio.create_task(_run_llm())

        try:
            while not llm_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(llm_task), timeout=_HEARTBEAT_INTERVAL
                    )
                except asyncio.TimeoutError:
                    if not llm_task.done():
                        yield AgentResponse.status(
                            "Still working...",
                            agent=self.agent_name,
                            context_id=context_id,
                            task_id=task_id,
                        )

            await llm_task

            final_response = result_holder.get('response')
            if final_response:
                yield AgentResponse.text(final_response)
            else:
                yield AgentResponse.text("No response generated")

        except Exception as e:
            abi_logging(f'[❌] Error in {self.agent_name}: {e}', level='error')
            if not llm_task.done():
                llm_task.cancel()
            yield AgentResponse.error(str(e))

    def get_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "name": self.agent_name,
            "description": self.description,
            "content_types": self.content_types,
        }

    @staticmethod
    async def check_health(agent_url: str, agent_name: str = "unknown") -> Dict[str, Any]:
        """Check if a remote agent is online and responding.

        Can be called before sending A2A messages to verify the target
        agent is reachable.  Works with any agent URL (permanent or
        ephemeral).

        Args:
            agent_url: Base URL of the agent (e.g. ``http://planner:11437``).
            agent_name: Display name for logging (optional).

        Returns:
            Dict with ``status`` (healthy/unhealthy/timeout/error),
            ``response_time_ms``, and ``status_code``.
        """
        import time

        import httpx

        abi_logging(f"[🏥] Health check: {agent_name} at {agent_url}")

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{agent_url}/health")
            elapsed_ms = round((time.time() - start) * 1000, 2)

            result = {
                "agent": agent_name,
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "url": agent_url,
                "response_time_ms": elapsed_ms,
                "status_code": resp.status_code,
            }
            abi_logging(f"[✅] {agent_name}: {result['status']} ({elapsed_ms}ms)")
            return result

        except httpx.TimeoutException:
            abi_logging(f"[⏰] {agent_name}: timeout")
            return {
                "agent": agent_name,
                "status": "timeout",
                "url": agent_url,
                "error": "Health check timeout (5s)",
            }
        except Exception as e:
            abi_logging(f"[❌] {agent_name}: {e}")
            return {
                "agent": agent_name,
                "status": "error",
                "url": agent_url,
                "error": str(e),
            }
