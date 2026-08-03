"""
AbiCore — Application runner for ABI agents.

Provides a FastAPI-style interface for starting agents with
decorator-based step/tool registration:

    from abi_core.agent import AbiCore
    from my_agent import MyAgent

    agent = AbiCore()

    @agent.step(name="clean_data")
    def clean_data(raw_input):
        return {"cleaned": raw_input.strip()}

    @agent.step(
        name="store_data",
        depends_on=["clean_data"],
        input_map={"data": "$clean_data.result"},
    )
    def store_data(data):
        return {"stored": True}

    @agent.tool(name="search_db")
    def search_db(query):
        return {"results": [...]}

    # MCP remote tool — no local function needed
    @agent.mcp_tool(
        name="bigquery_search",
        input_map={"query": "$input.user_query"},
    )

    agent.run(MyAgent())

Steps are deterministic DAG nodes executed in strict order.
Tools are also DAG nodes but additionally exposed as LangChain
tools so the LLM can invoke them on demand.
MCP tools are remote tools called via MCPToolkit with HMAC auth.

AbiCore auto-imports ``config`` and ``AGENT_CARD`` from the agent's
``config`` package (which must be on ``PYTHONPATH`` / in the same
directory as ``main.py``).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type

from abi_core.common.utils import abi_logging
from abi_core.common.async_task_store import (
    async_task_backend_from_env,
    log_task_event,
    new_async_task_id,
)
from abi_core.common.retry import retry_with_backoff


# ── Node type enum ──────────────────────────────────────────────

class _NodeType:
    TASK = "task"
    STEP = "step"
    TOOL = "tool"
    MCP_TOOL = "mcp_tool"


# ── Internal registry entries ────────────────────────────────────

@dataclass
class _RegisteredNode:
    """Metadata collected by @agent.step / @agent.tool / @agent.mcp_tool."""

    name: str
    fn: Optional[Callable] = None
    depends_on: List[str] = field(default_factory=list)
    input_map: Dict[str, str] = field(default_factory=dict)
    output_key: str = ""
    max_retries: int = 3
    retry_delay: float = 1.0
    node_type: str = _NodeType.STEP
    tools: List[str] = field(default_factory=list)


@dataclass
class _RegisteredTask:
    """Metadata collected by @agent.task."""

    name: str
    task_id: str
    fn: Callable
    tools: List[str] = field(default_factory=list)
    parallel: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class _RegisteredAsyncTask:
    """Metadata collected by @agent.task_async — fire-and-forget background
    work, launched via ``agent.execute_task_async(name, **kwargs)``."""

    name: str
    fn: Callable
    max_retries: int = 3
    base_delay: float = 1.0
    on_error: Optional[Callable] = None
    on_success: Optional[Callable] = None


@dataclass
class _RegisteredScheduledTask:
    """Metadata collected by @agent.task_schedule — a recurring job on
    AsyncIOScheduler. Every firing is gated by an OPA policy check AND an
    overlap check against the shared async-task store before the wrapped
    function runs — not "just a cron job"."""

    name: str
    fn: Callable
    trigger: str  # "cron" | "interval" | "date" — passed through to APScheduler
    trigger_args: Dict[str, Any] = field(default_factory=dict)
    overlap_policy: Literal["skip", "allow"] = "skip"
    max_concurrent: int = 1
    max_retries: int = 3
    base_delay: float = 1.0
    opa_bundle_path: str = "abi/scheduled_task/allow"
    fail_mode: Literal["open", "closed"] = "open"
    on_error: Optional[Callable] = None
    on_success: Optional[Callable] = None


# ── AbiCore ─────────────────────────────────────────────────────

class AbiCore:
    """Application runner that bootstraps and starts an ABI agent.

    Supports decorator-based registration of steps, tools, and MCP
    remote tools that are wired into a ``ToolExecutionGraph`` DAG
    before the agent starts.

    Args:
        host: Bind address (default ``"0.0.0.0"``).
        web_interface_cls: Optional web-interface class.
        interface_name: Display name for the web interface.
    """

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        web_interface_cls: Optional[Type] = None,
        interface_name: Optional[str] = None,
        config: Optional[Any] = None,
        agent_card: Optional[Any] = None,
    ):
        self.host = host
        self.web_interface_cls = web_interface_cls
        self.interface_name = interface_name
        self._registered_nodes: List[_RegisteredNode] = []
        self._registered_tasks: List[_RegisteredTask] = []
        self._registered_async_tasks: List[_RegisteredAsyncTask] = []
        self._registered_scheduled_tasks: List[_RegisteredScheduledTask] = []
        self._async_task_store = async_task_backend_from_env()
        self._agent_instance: Optional[Any] = None

        # Use provided config/agent_card or auto-import from config package
        if config is not None:
            self.config = config
            self.agent_card = agent_card
        else:
            try:
                import config as _cfg_module

                self.config = _cfg_module.config
                self.agent_card = _cfg_module.AGENT_CARD
            except ImportError as e:
                raise ImportError(
                    "AbiCore requires a 'config' package with 'config' and "
                    "'AGENT_CARD' exports. Make sure config/ is on PYTHONPATH, "
                    "or pass config= and agent_card= to AbiCore()."
                ) from e
            except AttributeError as e:
                raise AttributeError(
                    "The 'config' package must export both 'config' (AgentConfig) "
                    "and 'AGENT_CARD' (AgentCard)."
                ) from e

    # ── Decorators ──────────────────────────────────────────────

    def step(
        self,
        name: str,
        *,
        depends_on: Optional[List[str]] = None,
        input_map: Optional[Dict[str, str]] = None,
        output_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        tools: Optional[List[str]] = None,
    ) -> Callable:
        """Register a deterministic step in the execution DAG.

        Steps run in strict topological order — the LLM never decides
        when to call them.  Use ``input_map`` with ``$references`` to
        wire outputs between nodes.

        Args:
            name: Unique node id in the DAG.
            depends_on: List of node names this step depends on.
            input_map: ``{"param": "$other_node.key"}`` references.
            output_key: Key under which the return value is stored
                        (defaults to *name*).
            max_retries: Retry attempts on failure.
            retry_delay: Base delay between retries (exponential).
            tools: List of tool names that MUST be called during this step.
                   If declared, the framework enforces usage and falls back
                   to deterministic execution if the LLM doesn't call them.

        Returns:
            The original function (unmodified).
        """

        def decorator(fn: Callable) -> Callable:
            self._registered_nodes.append(
                _RegisteredNode(
                    name=name,
                    fn=fn,
                    depends_on=depends_on or [],
                    input_map=input_map or {},
                    output_key=output_key or name,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    node_type=_NodeType.STEP,
                    tools=tools or [],
                )
            )
            return fn

        return decorator

    def task(
        self,
        name: str,
        *,
        task_id: str,
        tools: Optional[List[str]] = None,
        parallel: Optional[List[str]] = None,
        depends_on: Optional[List[str]] = None,
    ) -> Callable:
        """Register a task — a programmatic orchestrator of steps.

        Unlike ``@agent.step()``, a task is not a DAG node. It is an
        async generator function that orchestrates steps by calling
        ``agent.execute_step()``, using ``asyncio.gather()`` for
        parallelism, and yielding ``AgentResponse`` objects for streaming.

        Steps defined inline inside a task function are automatically
        added to the agent's DAG.

        Args:
            name: Unique task name.
            task_id: Fixed ID for tracking and auditing.
            tools: Tool names available to steps within this task.
            parallel: Step names to execute in parallel (declarative mode).
            depends_on: Other task names that must complete first.

        Returns:
            The original function (unmodified).

        Example::

            @agent.task(name="process_query", task_id="task-001")
            async def process_query(query):
                from abi_core.agent.agent_response import AgentResponse
                yield AgentResponse.status("Gathering context...")
                context = await agent.execute_step("gather_context", query=query)
                yield AgentResponse.result(context)
        """

        def decorator(fn: Callable) -> Callable:
            self._registered_tasks.append(
                _RegisteredTask(
                    name=name,
                    task_id=task_id,
                    fn=fn,
                    tools=tools or [],
                    parallel=parallel or [],
                    depends_on=depends_on or [],
                )
            )
            return fn

        return decorator

    def task_async(
        self,
        name: str,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
        on_error: Optional[Callable] = None,
        on_success: Optional[Callable] = None,
    ) -> Callable:
        """Register a fire-and-forget background function.

        Unlike ``@agent.task()``, a task_async is not tied to the request
        that launches it: ``await agent.execute_task_async(name, **kwargs)``
        schedules it via ``asyncio.create_task`` and returns an id
        immediately, without waiting for it to finish. Failures retry with
        real exponential backoff (``base_delay * 2**attempt``) and every
        attempt/outcome is logged auditably; status is queryable afterwards
        via ``agent.get_async_task_status(async_task_id)``.

        Args:
            name: Unique name, looked up by ``execute_task_async``.
            max_retries: Retry attempts on failure (exponential backoff).
            base_delay: Base delay in seconds before the first retry.
            on_error: Optional ``(async_task_id, error) -> None`` callback,
                      called after retries are exhausted. Exceptions raised
                      by the callback itself are logged, never propagated.
            on_success: Optional ``(async_task_id, result) -> None``
                        callback, called once the function succeeds.

        Returns:
            The original function (unmodified).
        """

        def decorator(fn: Callable) -> Callable:
            self._registered_async_tasks.append(
                _RegisteredAsyncTask(
                    name=name,
                    fn=fn,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    on_error=on_error,
                    on_success=on_success,
                )
            )
            return fn

        return decorator

    def task_schedule(
        self,
        name: str,
        *,
        trigger: str,
        trigger_args: Optional[Dict[str, Any]] = None,
        overlap_policy: Literal["skip", "allow"] = "skip",
        max_concurrent: int = 1,
        max_retries: int = 3,
        base_delay: float = 1.0,
        opa_bundle_path: str = "abi/scheduled_task/allow",
        fail_mode: Literal["open", "closed"] = "open",
        on_error: Optional[Callable] = None,
        on_success: Optional[Callable] = None,
    ) -> Callable:
        """Register a recurring job on AsyncIOScheduler — governed, not just
        a cron job. Every firing is gated by:

        1. An overlap check against the shared async-task store
           (``overlap_policy="skip"``, the default, drops a firing if the
           previous one is still running — like Kubernetes CronJob's
           ``concurrencyPolicy=Forbid``).
        2. An OPA policy check (``abi/scheduled_task/allow`` by default) —
           fails OPEN (allows, with a logged warning) if OPA isn't
           configured/reachable, since Guardian/OPA are optional
           per-project infrastructure; pass ``fail_mode="closed"`` for a
           project that wants this gate to fail closed instead.

        Requires the ``apscheduler`` extra (``pip install
        "abi-core-ai[scheduler]"``) — only if at least one
        ``@agent.task_schedule`` is registered.

        Args:
            name: Unique job id.
            trigger: APScheduler trigger type — "cron" | "interval" | "date".
            trigger_args: Trigger kwargs passed through to APScheduler as-is
                          (e.g. ``{"seconds": 300}`` or ``{"hour": 3}``).
            overlap_policy: "skip" (default) drops overlapping firings;
                             "allow" permits up to ``max_concurrent``.
            max_concurrent: Max concurrent instances when ``overlap_policy``
                            is "allow" (ignored when "skip").
            max_retries: Retry attempts on failure (exponential backoff).
            base_delay: Base delay in seconds before the first retry.
            opa_bundle_path: OPA data path queried for the allow decision.
            fail_mode: "open" (default) allows when OPA is unreachable;
                       "closed" denies.
            on_error: Optional ``(async_task_id, error) -> None`` callback.
            on_success: Optional ``(async_task_id, result) -> None`` callback.

        Returns:
            The original function (unmodified).
        """

        def decorator(fn: Callable) -> Callable:
            self._registered_scheduled_tasks.append(
                _RegisteredScheduledTask(
                    name=name,
                    fn=fn,
                    trigger=trigger,
                    trigger_args=trigger_args or {},
                    overlap_policy=overlap_policy,
                    max_concurrent=max_concurrent,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    opa_bundle_path=opa_bundle_path,
                    fail_mode=fail_mode,
                    on_error=on_error,
                    on_success=on_success,
                )
            )
            return fn

        return decorator

    async def execute_step(self, step_name: str, **kwargs) -> dict:
        """Execute a registered step by name with the given inputs.

        Intended for use inside ``@agent.task`` functions to call
        individual steps programmatically.

        Args:
            step_name: Name of the step registered via ``@agent.step``.
            **kwargs: Input parameters passed directly to the step function.

        Returns:
            The step function's return value (a dict).

        Raises:
            KeyError: If ``step_name`` is not registered.
            TypeError: If the step function is not callable.
        """
        node = next(
            (n for n in self._registered_nodes if n.name == step_name),
            None,
        )
        if node is None:
            raise KeyError(
                f"Step '{step_name}' not found. "
                f"Registered steps: {[n.name for n in self._registered_nodes]}"
            )
        if node.fn is None:
            raise TypeError(f"Step '{step_name}' has no callable function (MCP tool?)")

        import inspect

        # Drop system-context kwargs (context_id/task_id) if the step doesn't
        # declare them, so a task can forward session context uniformly without
        # breaking steps that only take (query). Other kwargs pass through
        # unchanged, so a genuine typo still raises.
        kwargs = self._filter_system_kwargs(node.fn, kwargs)

        if inspect.isasyncgenfunction(node.fn):
            # Async generator step — collect all yielded values
            result = {}
            async for chunk in node.fn(**kwargs):
                if isinstance(chunk, dict):
                    result.update(chunk)
            return result
        elif inspect.iscoroutinefunction(node.fn):
            return await node.fn(**kwargs)
        else:
            return node.fn(**kwargs)

    @staticmethod
    def _filter_system_kwargs(fn, kwargs: dict) -> dict:
        """Drop framework-injected system kwargs the function doesn't accept.

        Only ``context_id`` and ``task_id`` are filtered (they're offered by the
        framework/tasks for session propagation). Any other kwarg is left as-is
        so a real typo still surfaces as a TypeError. If ``fn`` has ``**kwargs``,
        nothing is dropped.
        """
        import inspect

        _SYSTEM = ("context_id", "task_id", "context_snapshot")
        try:
            params = inspect.signature(fn).parameters
        except (ValueError, TypeError):
            return kwargs
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return kwargs
        return {
            k: v for k, v in kwargs.items()
            if k not in _SYSTEM or k in params
        }

    def get_task_metadata(self) -> list:
        """Return metadata for all registered tasks.

        Useful for the Builder to know which tools each task needs,
        and for the Semantic Layer to register tasks as discoverable units.

        Returns:
            List of dicts with name, task_id, tools, depends_on for each task.
        """
        return [
            {
                "name": t.name,
                "task_id": t.task_id,
                "tools": t.tools,
                "parallel": t.parallel,
                "depends_on": t.depends_on,
            }
            for t in self._registered_tasks
        ]

    async def execute_task(self, task_name: str, **kwargs):
        """Execute a registered task by name and yield its responses.

        Intended for use inside ``@agent.task`` functions to invoke
        other tasks programmatically (task composition).

        Args:
            task_name: Name of the task registered via ``@agent.task``.
            **kwargs: Input parameters passed directly to the task function.

        Yields:
            Responses from the task (typically AgentResponse objects).

        Raises:
            KeyError: If ``task_name`` is not registered.
            TypeError: If the task function is not callable.
        """
        if not hasattr(self, '_registered_tasks') or not self._registered_tasks:
            raise KeyError(f"No tasks registered. Cannot execute task '{task_name}'")

        task_entry = next(
            (t for t in self._registered_tasks if t.name == task_name),
            None,
        )
        if task_entry is None:
            raise KeyError(
                f"Task '{task_name}' not found. "
                f"Registered tasks: {[t.name for t in self._registered_tasks]}"
            )

        import inspect
        task_fn = task_entry.fn
        if task_fn is None:
            raise TypeError(f"Task '{task_name}' has no callable function")

        # Forward session context uniformly; drop context_id/task_id if the
        # target task doesn't declare them (see _filter_system_kwargs).
        kwargs = self._filter_system_kwargs(task_fn, kwargs)

        # Tasks are async generators that yield AgentResponse
        if inspect.isasyncgenfunction(task_fn):
            async for response in task_fn(**kwargs):
                yield response
        elif inspect.iscoroutinefunction(task_fn):
            # Non-generator async function — wrap result
            result = await task_fn(**kwargs)
            yield result
        else:
            raise TypeError(f"Task '{task_name}' must be an async function")

    # ── Background / scheduled tasks ────────────────────────────

    def _find_async_task(self, task_name: str) -> _RegisteredAsyncTask:
        entry = next((t for t in self._registered_async_tasks if t.name == task_name), None)
        if entry is None:
            raise KeyError(
                f"task_async '{task_name}' not found. "
                f"Registered: {[t.name for t in self._registered_async_tasks]}"
            )
        return entry

    async def execute_task_async(
        self, task_name: str, *, context_id: Optional[str] = None, **kwargs
    ) -> str:
        """Launch a @agent.task_async function in the background and return
        immediately with an id to poll via ``get_async_task_status``.

        Snapshots the caller's session context (if any) BEFORE scheduling —
        never re-resolved by ``context_id`` alone inside the background
        coroutine, since the in-memory session backend is per-pod and the
        background task can outlive/outrun the request that launched it.
        """
        entry = self._find_async_task(task_name)
        async_task_id = new_async_task_id()

        context_snapshot: Dict[str, Any] = {}
        if context_id and self._agent_instance is not None and getattr(
            self._agent_instance, "session_backend", None
        ):
            context_snapshot = await self._agent_instance.session_backend.get_context(context_id)

        await self._async_task_store.create(async_task_id, task_name, context_id)

        import asyncio

        asyncio.create_task(
            self._execute_and_audit(
                fn=entry.fn,
                name=entry.name,
                async_task_id=async_task_id,
                max_retries=entry.max_retries,
                base_delay=entry.base_delay,
                on_error=entry.on_error,
                on_success=entry.on_success,
                context_id=context_id,
                context_snapshot=context_snapshot,
                kwargs=kwargs,
            )
        )
        return async_task_id

    async def get_async_task_status(self, async_task_id: str) -> Optional[dict]:
        """In-process status lookup for a task_async/task_schedule run —
        the hook point for the settled "consult via A2A task_id" reuse; no
        new HTTP route. Returns None if the id is unknown/expired."""
        record = await self._async_task_store.get(async_task_id)
        return record.to_dict() if record else None

    async def get_session_context(self, context_id: str) -> Dict[str, Any]:
        """Passthrough to the running AbiAgent's session context — a
        ``@agent.task`` function only sees the AbiCore instance (``agent``
        in scaffolded code), not the AbiAgent subclass that actually owns
        ``session_backend``. Needed for framework-level capabilities like
        ``abi_core.agent.plan_confirmation`` to work from a plain task.
        Returns ``{}`` if called before ``.run()`` has set up the agent
        instance (shouldn't happen at request-serving time)."""
        if self._agent_instance is None:
            return {}
        return await self._agent_instance.get_session_context(context_id)

    async def update_session_context(self, context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Passthrough to the running AbiAgent's session context — see
        ``get_session_context`` for why this exists."""
        if self._agent_instance is None:
            return {}
        return await self._agent_instance.update_session_context(context_id, patch)

    async def _execute_and_audit(
        self,
        *,
        fn: Callable,
        name: str,
        async_task_id: str,
        max_retries: int,
        base_delay: float,
        on_error: Optional[Callable],
        on_success: Optional[Callable],
        context_id: Optional[str],
        context_snapshot: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> None:
        """Shared runner for task_async and task_schedule firings: retries
        with real exponential backoff, logs every attempt/outcome
        auditably, flushes those logs itself (independent of any HTTP
        request's lifecycle), writes a breadcrumb back into session
        context, and never lets a callback or an unexpected crash leave the
        record stuck in "running" (which would permanently block
        overlap_policy="skip" for this job name)."""
        import inspect

        call_kwargs = self._filter_system_kwargs(
            fn, {**kwargs, "context_id": context_id, "context_snapshot": context_snapshot}
        )

        async def _call():
            result = fn(**call_kwargs)
            if inspect.isasyncgenfunction(fn):
                collected: Dict[str, Any] = {}
                async for chunk in result:
                    if isinstance(chunk, dict):
                        collected.update(chunk)
                return collected
            if inspect.isawaitable(result):
                return await result
            return result

        attempts = 0

        async def _on_retry(attempt: int, exc: BaseException) -> None:
            nonlocal attempts
            attempts = attempt
            await self._async_task_store.bump_attempts(async_task_id, attempt)
            log_task_event(
                "task_async_attempt", task_name=name, async_task_id=async_task_id,
                attempt=attempt, max_retries=max_retries, status="running", error=str(exc),
                context_id=context_id,
            )

        try:
            try:
                result = await retry_with_backoff(
                    _call, max_retries=max_retries, base_delay=base_delay, on_retry=_on_retry,
                )
            except Exception as exc:  # noqa: BLE001 — final failure after all retries
                attempts = max(attempts, 1)
                error_str = str(exc)
                await self._async_task_store.mark_failed(async_task_id, error_str)
                log_task_event(
                    "task_async_failure", task_name=name, async_task_id=async_task_id,
                    attempt=attempts, max_retries=max_retries, status="failed",
                    error=error_str, context_id=context_id,
                )
                if on_error is not None:
                    try:
                        hook = on_error(async_task_id, error_str)
                        if inspect.isawaitable(hook):
                            await hook
                    except Exception as cb_exc:  # noqa: BLE001 — a broken callback must not
                        abi_logging(  # lose the already-recorded failure or crash the runner
                            f"[⚠️] task_async on_error callback for '{name}' raised: {cb_exc}",
                            level="warning",
                        )
            else:
                await self._async_task_store.mark_done(async_task_id, result)
                log_task_event(
                    "task_async_success", task_name=name, async_task_id=async_task_id,
                    attempt=max(attempts, 1), max_retries=max_retries, status="done",
                    context_id=context_id,
                )
                if on_success is not None:
                    try:
                        hook = on_success(async_task_id, result)
                        if inspect.isawaitable(hook):
                            await hook
                    except Exception as cb_exc:  # noqa: BLE001
                        abi_logging(
                            f"[⚠️] task_async on_success callback for '{name}' raised: {cb_exc}",
                            level="warning",
                        )

            await self._write_async_task_breadcrumb(context_id, async_task_id, name)

        except BaseException as crash:  # noqa: BLE001 — a crash in the runner itself must
            try:  # still mark the record failed, or overlap_policy="skip" locks up forever
                await self._async_task_store.mark_failed(async_task_id, f"Runner crashed: {crash}")
                log_task_event(
                    "task_async_failure", task_name=name, async_task_id=async_task_id,
                    attempt=max(attempts, 1), max_retries=max_retries, status="failed",
                    error=f"Runner crashed: {crash}", context_id=context_id,
                )
            except Exception:  # noqa: BLE001 — best-effort even in the crash path
                pass
        finally:
            try:
                from abi_core.common.utils import flush_logs

                await flush_logs(task_id=f"async-{async_task_id}")
            except Exception:  # noqa: BLE001 — never let log flushing mask the real outcome
                pass

    async def _write_async_task_breadcrumb(
        self, context_id: Optional[str], async_task_id: str, name: str
    ) -> None:
        if not context_id or self._agent_instance is None:
            return
        backend = getattr(self._agent_instance, "session_backend", None)
        if backend is None:
            return
        try:
            record = await self._async_task_store.get(async_task_id)
            if record is None:
                return
            current = await backend.get_context(context_id)
            history = list(current.get("task_async_history", []))
            history.append({
                "async_task_id": async_task_id,
                "task_name": name,
                "status": record.status,
                "started_at": record.started_at,
                "finished_at": record.finished_at,
                "attempts": record.attempts,
                "error": record.error,
            })
            history = history[-20:]  # capped — bound growth over a long-lived context_id
            await backend.update_context(context_id, {"task_async_history": history})
        except Exception as e:  # noqa: BLE001 — breadcrumb is best-effort, never blocking
            abi_logging(f"[⚠️] Could not write task_async breadcrumb: {e}", level="warning")

    def _find_scheduled_task(self, task_name: str) -> Optional[_RegisteredScheduledTask]:
        return next((t for t in self._registered_scheduled_tasks if t.name == task_name), None)

    async def _run_scheduled_task(self, entry: _RegisteredScheduledTask) -> None:
        """APScheduler job body — overlap check, then OPA gate, then run.
        Order matters: if the firing is about to be skipped for overlap,
        there's no point asking OPA for permission first."""
        if entry.overlap_policy == "skip" and await self._async_task_store.is_running(entry.name):
            log_task_event(
                "task_schedule_skipped_overlap", task_name=entry.name, async_task_id="-",
                status="skipped",
            )
            return

        from abi_core.security.scheduled_task_policy import check_scheduled_task_policy

        agent_name = getattr(self.config, "AGENT_NAME", getattr(self.config, "AGENT_DISPLAY_NAME", "unknown"))
        allowed, reason = await check_scheduled_task_policy(
            agent_name, entry.name, entry.trigger,
            bundle_path=entry.opa_bundle_path, fail_mode=entry.fail_mode,
        )
        if not allowed:
            log_task_event(
                "task_schedule_denied", task_name=entry.name, async_task_id="-",
                status="denied", error=reason,
            )
            return

        async_task_id = new_async_task_id()
        await self._async_task_store.create(async_task_id, entry.name, context_id=None)
        await self._execute_and_audit(
            fn=entry.fn, name=entry.name, async_task_id=async_task_id,
            max_retries=entry.max_retries, base_delay=entry.base_delay,
            on_error=entry.on_error, on_success=entry.on_success,
            context_id=None, context_snapshot=None, kwargs={},
        )

    def _build_scheduler_jobs(self) -> List[dict]:
        """Job specs for AsyncIOScheduler, built at .run() time and handed
        down to agent_factory/start_server — the actual AsyncIOScheduler()
        instance is only constructed inside Starlette's on_startup hook,
        once a real event loop exists (see agent_factory.py/a2a_server.py)."""
        jobs = []
        for entry in self._registered_scheduled_tasks:
            def _make_job(entry=entry):  # default-arg capture — avoids the
                async def _job():        # classic late-binding closure bug
                    await self._run_scheduled_task(entry)
                return _job

            jobs.append({
                "id": entry.name,
                "func": _make_job(),
                "trigger": entry.trigger,
                "trigger_args": entry.trigger_args,
                "max_instances": 1 if entry.overlap_policy == "skip" else max(entry.max_concurrent, 2),
            })
        return jobs

    def tool(
        self,
        name: str,
        *,
        depends_on: Optional[List[str]] = None,
        input_map: Optional[Dict[str, str]] = None,
        output_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Callable:
        """Register a tool in the execution DAG.

        Tools are DAG nodes like steps, but they are additionally
        converted to LangChain tools and injected into the agent so
        the LLM can also invoke them on demand.

        Args:
            name: Unique node id in the DAG.
            depends_on: List of node names this tool depends on.
            input_map: ``{"param": "$other_node.key"}`` references.
            output_key: Key under which the return value is stored
                        (defaults to *name*).
            max_retries: Retry attempts on failure.
            retry_delay: Base delay between retries (exponential).

        Returns:
            The original function (unmodified).
        """

        def decorator(fn: Callable) -> Callable:
            self._registered_nodes.append(
                _RegisteredNode(
                    name=name,
                    fn=fn,
                    depends_on=depends_on or [],
                    input_map=input_map or {},
                    output_key=output_key or name,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    node_type=_NodeType.TOOL,
                )
            )
            return fn

        return decorator

    def mcp_tool(
        self,
        name: str,
        *,
        depends_on: Optional[List[str]] = None,
        input_map: Optional[Dict[str, str]] = None,
        output_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Register a remote MCP tool in the execution DAG.

        Unlike ``@agent.tool()``, this does NOT require a local function.
        The tool is called remotely via ``MCPToolkit`` with HMAC
        authentication from the agent card.

        Can be used as a bare decorator (no function) or wrapping a
        function that pre/post-processes the MCP call.

        Bare usage (no function — pure MCP call)::

            @agent.mcp_tool(
                name="bigquery_search",
                input_map={"query": "$input.user_query"},
            )

        With wrapper function (pre/post processing)::

            @agent.mcp_tool(name="bigquery_search")
            async def bigquery_search(query):
                # pre-process, call is handled by MCPToolkit
                return {"query": sanitize(query)}

        Args:
            name: MCP tool name (must match the tool registered in the
                  semantic layer / MCP server).
            depends_on: List of node names this tool depends on.
            input_map: ``{"param": "$other_node.key"}`` references.
            output_key: Key under which the return value is stored
                        (defaults to *name*).
            max_retries: Retry attempts on failure.
            retry_delay: Base delay between retries (exponential).

        Returns:
            Decorator or registers directly if used bare.
        """
        node_entry = _RegisteredNode(
            name=name,
            fn=None,  # Will use MCPToolkit if no fn provided
            depends_on=depends_on or [],
            input_map=input_map or {},
            output_key=output_key or name,
            max_retries=max_retries,
            retry_delay=retry_delay,
            node_type=_NodeType.MCP_TOOL,
        )

        def decorator(fn: Callable) -> Callable:
            node_entry.fn = fn
            self._registered_nodes.append(node_entry)
            return fn

        # Support bare usage: @agent.mcp_tool(name="x") with no function
        # We register immediately; if a function follows, decorator updates fn
        self._registered_nodes.append(node_entry)

        def maybe_decorator(fn_or_none=None):
            if fn_or_none is not None and callable(fn_or_none):
                # Remove the bare entry, re-add with fn
                if node_entry in self._registered_nodes:
                    self._registered_nodes.remove(node_entry)
                node_entry.fn = fn_or_none
                self._registered_nodes.append(node_entry)
                return fn_or_none
            return fn_or_none

        return maybe_decorator

    # ── DAG construction ────────────────────────────────────────

    def _build_tool_graph(self):
        """Build a ToolExecutionGraph from registered steps/tools.

        Returns None if no steps/tools were registered.
        """
        if not self._registered_nodes:
            return None

        from abi_core.common.tool_graph import ToolExecutionGraph, ToolGraphNode

        graph = ToolExecutionGraph(graph_id="agent")

        for entry in self._registered_nodes:
            if entry.node_type == _NodeType.MCP_TOOL and entry.fn is None:
                # Pure MCP tool — use tool name for remote call
                graph.add_node(
                    ToolGraphNode(
                        id=entry.name,
                        tool=entry.name,  # MCPToolkit resolves this
                        input_map=entry.input_map,
                        output_key=entry.output_key,
                        depends_on=entry.depends_on,
                        max_retries=entry.max_retries,
                        retry_delay=entry.retry_delay,
                    )
                )
            else:
                # Local function (step, tool, or mcp_tool with wrapper)
                graph.add_node(
                    ToolGraphNode(
                        id=entry.name,
                        fn=entry.fn,
                        input_map=entry.input_map,
                        output_key=entry.output_key,
                        depends_on=entry.depends_on,
                        max_retries=entry.max_retries,
                        retry_delay=entry.retry_delay,
                    )
                )

        steps = sum(1 for n in self._registered_nodes if n.node_type == _NodeType.STEP)
        tools = sum(1 for n in self._registered_nodes if n.node_type == _NodeType.TOOL)
        mcp = sum(1 for n in self._registered_nodes if n.node_type == _NodeType.MCP_TOOL)
        abi_logging(
            f"[🔧] ToolExecutionGraph built: {len(self._registered_nodes)} nodes "
            f"({steps} steps, {tools} tools, {mcp} mcp_tools)"
        )
        return graph

    def _collect_langchain_tools(self) -> List:
        """Convert @agent.tool() functions into LangChain StructuredTools."""
        tool_nodes = [n for n in self._registered_nodes if n.node_type == _NodeType.TOOL]
        if not tool_nodes:
            return []

        from langchain_core.tools import StructuredTool

        lc_tools = []
        for entry in tool_nodes:
            lc_tools.append(
                StructuredTool.from_function(
                    func=entry.fn,
                    name=entry.name,
                    description=entry.fn.__doc__ or f"Tool: {entry.name}",
                )
            )

        abi_logging(f"[🔧] {len(lc_tools)} LangChain tools created from @agent.tool()")
        return lc_tools

    # ── Run ─────────────────────────────────────────────────────

    def run(self, agent_instance) -> int:
        """Start the agent with A2A server and optional web interface.

        Auto-discovers and imports ``tools``, ``steps``, and ``tasks``
        modules from the agent's directory if they exist. This registers
        any decorators defined in those files without requiring explicit
        imports in main.py.

        Args:
            agent_instance: An already-instantiated AbiAgent subclass.

        Returns:
            Exit code (0 = clean shutdown, 1 = error).
        """
        # Auto-discover sibling modules (tools.py, steps.py, tasks.py).
        # Distinguish "module doesn't exist" (fine to skip) from "module exists
        # but fails to import" (a real error). Swallowing the latter leaves the
        # DAG empty and the agent fails cryptically at runtime with
        # "Registered steps: []" — a silent failure. Surface it loudly instead.
        import importlib
        import importlib.util
        import traceback
        for module_name in ("tools", "steps", "tasks"):
            if importlib.util.find_spec(module_name) is None:
                continue  # module genuinely not present — skip
            try:
                importlib.import_module(module_name)
            except Exception as e:  # noqa: BLE001 — module exists but broke on import
                tb = traceback.format_exc()
                abi_logging(
                    f"[❌] Failed to import '{module_name}.py' — its decorators "
                    f"(@agent.step/@agent.task/@agent.tool) will NOT be registered, "
                    f"so the agent will fail at runtime. Fix the import error:\n{e}\n{tb}",
                    level="error",
                )
                raise

        from abi_core.agent.agent_factory import agent_factory

        # Build DAG and inject into agent
        tool_graph = self._build_tool_graph()
        if tool_graph is not None:
            agent_instance.tool_graph = tool_graph

        # Inject LangChain tools from @agent.tool() into agent
        lc_tools = self._collect_langchain_tools()
        if lc_tools:
            if hasattr(agent_instance, "extra_tools"):
                agent_instance.extra_tools.extend(lc_tools)
            else:
                agent_instance.extra_tools = lc_tools

        # Inject registered tasks and execute_step into agent
        if self._registered_tasks:
            agent_instance._registered_tasks = {
                t.name: t for t in self._registered_tasks
            }
            # Bind execute_step so tasks can call agent.execute_step(...)
            agent_instance._abi_core = self

        # Back-reference so execute_task_async/_run_scheduled_task can reach
        # agent_instance.session_backend for context snapshots/breadcrumbs.
        # Harmless even when neither task_async nor task_schedule is used.
        self._agent_instance = agent_instance

        scheduler_jobs = None
        if self._registered_scheduled_tasks:
            # Fail fast at boot, not silently the first time a job should
            # have fired hours later.
            try:
                import apscheduler  # noqa: F401
            except ImportError:
                abi_logging(
                    "[❌] @agent.task_schedule is registered but 'apscheduler' is "
                    "not installed. Install the extra: pip install "
                    "\"abi-core-ai[scheduler]\"",
                    level="error",
                )
                raise

            # Publish a discoverable default-allow rule ONLY if this project
            # actually provisioned OPA and doesn't already have one — never
            # overwrites a customized rule. The OPA gate is already fail-open
            # (see check_scheduled_task_policy), so this is about operator
            # discoverability, not correctness.
            import os as _os
            if _os.getenv("OPA_URL"):
                from abi_core.opa.scheduled_task_policies import write_default_scheduled_task_policy
                write_default_scheduled_task_policy("./opa/scheduled_task_policies.rego")

            scheduler_jobs = self._build_scheduler_jobs()

        return agent_factory(
            agent_instance,
            self.config,
            self.agent_card,
            host=self.host,
            web_interface_cls=self.web_interface_cls,
            interface_name=self.interface_name,
            scheduler_jobs=scheduler_jobs,
        )
