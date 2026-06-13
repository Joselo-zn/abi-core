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
from typing import Any, Callable, Dict, List, Optional, Type

from abi_core.common.utils import abi_logging


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
        # Auto-discover sibling modules (tools.py, steps.py, tasks.py)
        import importlib
        for module_name in ("tools", "steps", "tasks"):
            try:
                importlib.import_module(module_name)
            except ImportError:
                pass
            except Exception as e:
                abi_logging(
                    f"[⚠️] Failed to auto-import '{module_name}': {e}",
                    level="warning",
                )

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

        return agent_factory(
            agent_instance,
            self.config,
            self.agent_card,
            host=self.host,
            web_interface_cls=self.web_interface_cls,
            interface_name=self.interface_name,
        )
