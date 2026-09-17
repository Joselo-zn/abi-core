"""
Base ABI Agent Class
Core agent functionality for ABI Framework
"""

import asyncio
import os
from typing import Any, Dict, List, AsyncIterable, Optional, TYPE_CHECKING

from abi_core.common.utils import abi_logging

if TYPE_CHECKING:
    from abi_core.session import SessionBackend
from abi_core.agent.llm_provider import create_llm
from abi_core.agent.agent_response import AgentResponse

# Heartbeat interval in seconds — must be under proxy timeout (CloudFront = 30s)
_HEARTBEAT_INTERVAL = 15

# Optional, opt-in safety net for _run_with_heartbeat() — NOT applied by
# default anywhere (see _run_with_heartbeat's docstring). A single constant
# can't fit every request: the same call site legitimately needs anywhere
# from ~13s to 3+ minutes depending on the actual task, not the call site
# itself — measured live, same code path, same env: 164s one run, 179s
# (timed out) the next. Guessing one global number was the bug, not a call
# site that was miscategorized. Kept only for a caller that explicitly
# wants a safety net for a specific coroutine it knows isn't bounded
# internally yet. See .abi/specs/heartbeat-timeout-redesign.md
# ("Revisión 2026-09-11").
_DEFAULT_MAX_WAIT = float(os.getenv("ABI_REASONING_TIMEOUT", "180"))
_DEFAULT_DAG_MAX_WAIT = float(os.getenv("ABI_DAG_MAX_WAIT", "900"))


class HeartbeatTimeoutError(TimeoutError):
    """Raised by ``_run_with_heartbeat`` only when a caller passes an
    explicit ``max_wait`` and it elapses — the default (``max_wait=None``)
    never raises this. Heartbeats are yielded live as they occur (see
    ``_run_with_heartbeat``'s docstring), so unlike the first version of
    this class, there is nothing left to attach here: anything generated
    before the cutoff was already forwarded to the caller in real time, not
    batched for delivery after the fact. See
    .abi/specs/heartbeat-timeout-redesign.md.
    """


class _HeartbeatDone:
    """Sentinel wrapping the final result yielded by ``_run_with_heartbeat``
    / ``_run_llm_turn`` — distinguishes it from the ``AgentResponse``
    heartbeats yielded live along the way::

        result = None
        async for item in self._run_with_heartbeat(coro, ...):
            if isinstance(item, _HeartbeatDone):
                result = item.value
            else:
                yield item
    """

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


def _supported_kwargs(fn, **candidates):
    """Return only the kwargs that ``fn``'s signature accepts.

    Lets the framework offer session context (``context_id``/``task_id``) to a
    task/step without breaking functions that only declare ``(query)``. If the
    function has ``**kwargs``, all candidates pass through.
    """
    import inspect

    try:
        params = inspect.signature(fn).parameters
    except (ValueError, TypeError):
        return dict(candidates)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(candidates)
    return {k: v for k, v in candidates.items() if k in params}


class AbiAgent:
    """Base class for all ABI agents.

    Handles LLM creation, LangChain agent wiring, and a default
    ``stream()`` implementation so subclasses only need to pass
    configuration.  Override ``stream()`` for custom behaviour.

    The optional ``tool_graph`` attribute is injected by ``AbiCore``
    when tasks/steps/tools are registered via ``@app.step()`` / ``@app.tool()``
    decorators.  Subclasses can use ``self.tool_graph`` to execute
    deterministic DAG pipelines. ``@app.tool()`` functions declared WITH
    ``depends_on`` become DAG nodes (Path A, deterministic — their input comes
    from another step's output). Declared WITHOUT ``depends_on`` they become
    LLM-callable tools instead (``self.extra_tools``): in ``stream()``, if the
    DAG runs and standalone tools are registered, the LLM gets a turn *after*
    the DAG with those tools bound, rather than the DAG's result being
    returned immediately — see .abi/tsd/2026-08-23-agent-tool-dag-llm-coexist.md.

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
        session_backend: Optional["SessionBackend"] = None,
        middleware: List = None,
    ):
        self.agent_name = agent_name
        self.description = description
        self.llm_config = llm_config
        self.content_types = content_types or ["text", "text/plain"]

        # Session backend — where conversation context lives.
        # Default: in-memory (per-pod). Inject a RedisSessionBackend (or set
        # SESSION_BACKEND=redis and pass session_backend_from_env()) for
        # multi-pod / load-balanced deployments. See abi_core.session.
        if session_backend is None:
            from abi_core.session import session_backend_from_env
            session_backend = session_backend_from_env()
        self.session_backend = session_backend

        # Injected by AbiCore when @app.task()/@app.tool() are used
        self.tool_graph = None  # Optional[ToolExecutionGraph]
        self.extra_tools: List = []  # LangChain tools from standalone @app.tool() (no depends_on)

        # Create LLM via unified provider
        self.llm = create_llm(llm_config)

        # self.agent gets rebuilt by _build_langchain_agent() once AbiCore.run()
        # populates extra_tools (that happens AFTER __init__, on the already-built
        # instance — see AbiCore.run()) — so these need to be kept around, not just
        # consumed once here.
        self._base_tools = tools or []
        self._system_prompt = system_prompt
        self._middleware = middleware or []

        # Checkpointer for conversation memory (MemorySaver — in-process)
        from langgraph.checkpoint.memory import MemorySaver

        self.checkpointer = MemorySaver()

        self._build_langchain_agent()

        abi_logging(f"[🚀] {agent_name} agent ready")

    def _build_langchain_agent(self) -> None:
        """(Re)build ``self.agent`` from ``self._base_tools + self.extra_tools``.

        Called once from ``__init__``, and again by ``AbiCore.run()`` after it
        collects standalone ``@agent.tool()`` functions into ``self.extra_tools``
        — that collection happens on the already-constructed instance, after
        ``__init__``'s own call already ran with an empty ``extra_tools``, so a
        rebuild is the only way those tools reach ``self.agent``'s bound tool list.
        """
        from langchain.agents import create_agent

        self.agent = create_agent(
            model=self.llm,
            tools=[*self._base_tools, *self.extra_tools],
            system_prompt=self._system_prompt,
            checkpointer=self.checkpointer,
            middleware=self._middleware,
        )

    # ── Session management ──────────────────────────────────────
    #
    # Conversation context lives in ``self.session_backend`` (a
    # ``SessionBackend``), NOT in per-process RAM. Default backend is
    # in-memory; inject a Redis backend for multi-pod / LB-safe state.
    # These methods are ``async`` so the Redis backend can await I/O without
    # blocking the event loop; the in-memory backend is a near-free async.

    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Return accumulated conversation context for a session."""
        return await self.session_backend.get_context(session_id)

    async def update_session_context(
        self, session_id: str, patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge ``patch`` into the session's conversation context."""
        return await self.session_backend.update_context(session_id, patch)

    async def process_answer(self, session_id: str, query: str) -> tuple:
        """Detect if query is an answer (``id: text``), update context.

        Returns:
            ``(context, was_answer)`` — the session context dict and
            whether the query was parsed as an answer.
        """
        context = await self.session_backend.get_context(session_id)

        if context and ':' in query:
            parts = query.split(':', 1)
            answer_id = parts[0].strip()
            answer_text = parts[1].strip()
            context = await self.session_backend.update_context(
                session_id, {answer_id: answer_text}
            )
            abi_logging(f'[💬] Received answer for {answer_id}')
            return context, True

        return context, False

    async def clear_session(self, session_id: str) -> None:
        """Clear conversation context for a session."""
        await self.session_backend.clear_context(session_id)
        abi_logging(f"[🗑️] Cleared session {session_id}")

    # ── Session-scoped bookkeeping (generic — any agent may use these) ──
    #
    # Moved here from a private orchestrator-only copy — the logic never had
    # anything orchestrator-specific in it, so any agent (or a standalone
    # ``abi-core add agent`` project) that needs the same cross-turn
    # bookkeeping now inherits it instead of reimplementing it. See
    # .abi/specs/agent-session-bookkeeping-methods.md.

    async def record_error(self, context_id: str, error_type: str, message: str):
        """State goes to the session backend (LB/multi-pod safe), never to
        per-process RAM. See WORKING_RULES → "Perspectiva Local vs Global".

        ``last_error`` (no type suffix) is the most recent error regardless
        of type — a caller with a "next request awareness" point (e.g. the
        Orchestrator's ``build_routing_contract``) reads and consumes it on
        the very next read, no TTL/timestamp needed (overwritten on every
        call, so the latest write is always "the" last error by
        construction). See .abi/specs/orchestrator-last-error-awareness.md.
        """
        await self.update_session_context(context_id, {
            f"last_error_{error_type}": message,
            "last_error": message,
        })
        abi_logging(f"[📝] Error recorded in session {context_id}: {error_type}")

    async def record_pending_plan(self, context_id: str, plan: dict, original_query: str):
        """Record a plan awaiting the user's approve/reject/modify decision.
        See ``abi_core.agent.plan_confirmation`` for the actual bookkeeping."""
        from abi_core.agent.plan_confirmation import record_pending_plan as _record_pending_plan

        await _record_pending_plan(self.update_session_context, context_id, plan, original_query)

    async def clear_pending_plan(self, context_id: str):
        """Clear a pending plan once it's been approved/rejected/modified."""
        from abi_core.agent.plan_confirmation import clear_pending_plan as _clear_pending_plan

        await _clear_pending_plan(self.update_session_context, context_id)

    async def record_conversation_turn(
        self, context_id: str, query: str, response_text: str, window: int = 5
    ):
        """Append a turn to the session's rolling conversation window (session
        backend — LB/multi-pod safe, never per-process RAM). When the window
        overflows, the oldest turn is promoted to long-term memory (AMS, if
        configured — degrades silently otherwise) before being dropped, never
        just discarded. See WORKING_RULES → "Perspectiva Local vs Global" and
        .abi/specs/orchestrator-conversation-memory.md.
        """
        session_ctx = await self.get_session_context(context_id)
        turns = session_ctx.get("conversation_summary") or []
        turns.append({"user": query, "assistant": response_text})

        while len(turns) > window:
            oldest = turns.pop(0)
            from abi_core.memory import add_long_term_memory

            await add_long_term_memory(
                topic="conversation_history",
                task=context_id,
                content=f"User: {oldest['user']}\nAssistant: {oldest['assistant']}",
                context_id=context_id,
            )

        await self.update_session_context(context_id, {"conversation_summary": turns})

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

    async def _run_with_heartbeat(
        self, coro, context_id, task_id, status_msg, max_wait: Optional[float] = None,
    ):
        """Run a coroutine, yielding heartbeats live as they occur.

        Async generator. Executes *coro* in a background task and ``yield``s
        each ``AgentResponse.status()`` heartbeat the instant it's detected
        (every ``_HEARTBEAT_INTERVAL`` seconds of no progress) — not
        batched into a list handed back after the wait is over, which
        defeated the entire point of a heartbeat (keeping a streaming
        connection alive under a proxy's idle timeout — see
        ``_HEARTBEAT_INTERVAL``'s comment). The final item yielded is always
        a ``_HeartbeatDone`` wrapping *coro*'s own result:

            result = None
            async for item in self._run_with_heartbeat(coro, ...):
                if isinstance(item, _HeartbeatDone):
                    result = item.value
                else:
                    yield item

        ``max_wait`` is ``None`` by default — no external cap is imposed.
        Guessing one generic wall-clock value up front for every possible
        *coro* was the actual bug, not a badly-calibrated number: the same
        call site, same code path, genuinely needs anywhere from ~13s to
        3+ minutes depending on the request, not the call site itself
        (measured live: 164s one run, 179s — timed out — the next, same
        constant). *coro* is expected to bound its own real work internally
        instead (a DAG step's own ``timeout``, a subprocess's own
        ``timeout=``, an LLM call's own per-call bound) — this just relays
        progress and lets it run. Pass ``max_wait`` explicitly only for a
        specific *coro* known not to bound itself internally yet, as a
        temporary safety net. See .abi/specs/heartbeat-timeout-redesign.md
        ("Revisión 2026-09-11").

        Args:
            coro: Awaitable to execute.
            context_id: Context identifier for heartbeat metadata.
            task_id: Task identifier for heartbeat metadata.
            status_msg: Text shown in heartbeat status messages.
            max_wait: Optional seconds to wait before giving up. ``None``
                (default) imposes no cap.

        Yields:
            ``AgentResponse`` heartbeats as they occur, then a final
            ``_HeartbeatDone`` wrapping *coro*'s result.

        Raises:
            HeartbeatTimeoutError: Only if *max_wait* is given and elapses.
                Cancelling the underlying task is a cooperative request, not
                a guarantee — if *coro* is blocked on non-async work (e.g. a
                thread via ``asyncio.to_thread``), that work keeps running
                in the background regardless. See
                .abi/specs/heartbeat-timeout-redesign.md.
        """
        elapsed = 0.0
        task = asyncio.create_task(coro)

        while not task.done():
            if max_wait is not None:
                remaining = max_wait - elapsed
                if remaining <= 0:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass  # we're about to raise our own, clearer error below
                    raise HeartbeatTimeoutError(
                        f"Esto está tardando más de lo esperado (más de {int(max_wait)}s) — "
                        "probablemente el modelo está sobrecargado. Intentá de nuevo."
                    )
                # Cap each wait at whichever is smaller — the heartbeat interval
                # or what's left of max_wait — so max_wait values under
                # _HEARTBEAT_INTERVAL still cut in on time instead of silently
                # rounding up to the next 15s boundary (verified empirically: a
                # naive `timeout=_HEARTBEAT_INTERVAL` here never raises at all
                # for max_wait < 15, since the coroutine would already be done
                # or the loop exits before elapsed ever gets checked again).
                wait_chunk = min(_HEARTBEAT_INTERVAL, remaining)
            else:
                wait_chunk = _HEARTBEAT_INTERVAL

            try:
                await asyncio.wait_for(
                    asyncio.shield(task), timeout=wait_chunk
                )
            except asyncio.TimeoutError:
                elapsed += wait_chunk
                if not task.done():
                    yield AgentResponse.status(
                        status_msg,
                        agent=self.agent_name,
                        context_id=context_id,
                        task_id=task_id,
                    )

        yield _HeartbeatDone(task.result())

    async def _run_llm_turn(self, query: str, context_id: str, task_id: str):
        """Run one turn of ``self.agent.astream``, yielding heartbeats live
        and a final ``_HeartbeatDone(final_text)`` — same consumption
        pattern as ``_run_with_heartbeat`` (see its docstring).

        Shared by Path A (DAG then LLM, when standalone tools are registered)
        and Path B (LLM only) below — factored out so both go through the same
        heartbeat-wrapped call instead of duplicating the astream/heartbeat loop.
        """
        result_holder: Dict[str, Any] = {}

        async def _run_llm():
            inputs = {"messages": [{"role": "user", "content": query}]}
            thread_config = {"configurable": {"thread_id": context_id}}
            async for chunk in self.agent.astream(
                inputs, config=thread_config, stream_mode="updates"
            ):
                for _node_name, node_data in chunk.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            if hasattr(msg, 'content') and msg.content:
                                result_holder['response'] = msg.content

        async for item in self._run_with_heartbeat(_run_llm(), context_id, task_id, "Still working..."):
            if isinstance(item, _HeartbeatDone):
                yield _HeartbeatDone(result_holder.get('response'))
            else:
                yield item

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
        context, was_answer = await self.process_answer(context_id, query)

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
                # Propagate session context to the task, but only the kwargs its
                # signature accepts — so existing tasks with `(query)` keep
                # working while new ones can take `(query, context_id, task_id)`.
                # This carries the system context (context_id) across the hop so
                # steps can read/write session memory. See WORKING_RULES →
                # "Perspectiva Local vs Global".
                call_kwargs = _supported_kwargs(
                    task_fn, query=query, context_id=context_id, task_id=task_id
                )
                if inspect.isasyncgenfunction(task_fn):
                    async for chunk in task_fn(**call_kwargs):
                        yield chunk
                elif inspect.iscoroutinefunction(task_fn):
                    result = await task_fn(**call_kwargs)
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
                dag_result = None
                async for item in self._run_with_heartbeat(dag_coro, context_id, task_id, "Executing pipeline..."):
                    if isinstance(item, _HeartbeatDone):
                        dag_result = item.value
                    else:
                        yield item

                if dag_result.get("failed_node"):
                    yield AgentResponse.error(dag_result.get("error", "Pipeline failed"))
                    return

                # Return the last node's output as the result
                outputs = dag_result.get("node_outputs", {})
                completed = dag_result.get("completed_nodes", [])
                last_output = outputs.get(completed[-1]) if completed else None

                if not self.extra_tools:
                    # No standalone @agent.tool() registered — unchanged behavior.
                    if last_output is not None:
                        yield AgentResponse.result(last_output)
                    else:
                        yield AgentResponse.text("Completed")
                    return

                # Standalone tools ARE registered: give the LLM a turn after the
                # DAG instead of returning immediately, so those tools are
                # actually reachable — see .abi/tsd/2026-08-23-agent-tool-dag-llm-coexist.md.
                # Only agents that use bare @agent.tool() (no depends_on) pay for
                # this extra LLM call; everyone else keeps today's DAG-only path.
                dag_summary = _json.dumps(last_output) if last_output is not None else "Completed"
                llm_query = f"[Pipeline result]: {dag_summary}\n\nOriginal request: {query}"
                final_response = None
                async for item in self._run_llm_turn(llm_query, context_id, task_id):
                    if isinstance(item, _HeartbeatDone):
                        final_response = item.value
                    else:
                        yield item

                if final_response:
                    yield AgentResponse.text(final_response)
                elif last_output is not None:
                    yield AgentResponse.result(last_output)
                else:
                    yield AgentResponse.text("Completed")
                return

            except Exception as e:
                abi_logging(f'[❌] Error in {self.agent_name} DAG: {e}', level='error')
                yield AgentResponse.error(str(e))
                return

        # ── Path B: no tool_graph → use LLM agent ──────────────
        try:
            final_response = None
            async for item in self._run_llm_turn(query, context_id, task_id):
                if isinstance(item, _HeartbeatDone):
                    final_response = item.value
                else:
                    yield item

            if final_response:
                yield AgentResponse.text(final_response)
            else:
                yield AgentResponse.text("No response generated")

        except Exception as e:
            abi_logging(f'[❌] Error in {self.agent_name}: {e}', level='error')
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
