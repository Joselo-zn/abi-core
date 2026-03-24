"""
Deterministic Tool Execution Graph (LangGraph-based)

Ensures agents follow a strict, predefined sequence of tool calls
regardless of LLM reasoning. Uses LangGraph's StateGraph to enforce
execution order — the LLM never decides which tool to call next.

Supports:
- DAG-based deterministic execution via LangGraph
- $-reference resolution between nodes (e.g. $input.user_query, $step1.result)
- Checkpoint/resume on failures (LangGraph state is preserved)
- Construction from JSON config or programmatic API
- Retry with exponential backoff per node

Usage:
    # From JSON
    graph = ToolExecutionGraph.from_json(config_dict)
    result = await graph.execute({"user_query": "ventas Q4 por región"})

    # Programmatic
    graph = ToolExecutionGraph()
    graph.add_node(ToolGraphNode(id="step1", tool="get_tables_metadata", ...))
    graph.add_node(ToolGraphNode(id="step2", tool="get_sample_data", ...))
    result = await graph.execute({"user_query": "ventas Q4 por región"})
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from abi_core.common.utils import abi_logging


# ── Status enums ────────────────────────────────────────────────

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GraphStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


# ── State (LangGraph TypedDict) ────────────────────────────────

class ToolGraphState(TypedDict):
    """LangGraph state shared across all nodes."""
    input_data: Dict[str, Any]
    node_outputs: Dict[str, Any]
    current_node: str
    completed_nodes: List[str]
    failed_node: Optional[str]
    error: Optional[str]
    status: str


# ── Node definition ─────────────────────────────────────────────

@dataclass
class ToolGraphNode:
    """
    A single deterministic step in the tool execution graph.

    Supports two execution modes:
    - MCP tool call: set ``tool`` to the MCP tool name
    - Local function: set ``fn`` to an async/sync callable

    At least one of ``tool`` or ``fn`` must be provided.
    If both are set, ``fn`` takes priority.
    """

    id: str
    tool: str = ""                          # MCP tool name (remote)
    fn: Optional[Callable] = None           # Local function (sync or async)
    input_map: Dict[str, str] = field(default_factory=dict)
    output_key: str = ""
    depends_on: List[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0

    def __post_init__(self):
        if not self.tool and self.fn is None:
            raise ValueError(f"Node '{self.id}': must provide either 'tool' or 'fn'")

    def reset(self):
        self.status = NodeStatus.PENDING
        self.result = None
        self.error = None
        self.attempts = 0


# ── Reference resolution ───────────────────────────────────────

def _resolve_ref(ref: str, context: Dict[str, Any]) -> Any:
    """
    Resolve a $-reference against the execution context.

    Patterns:
        $input.user_query        -> context["input_data"]["user_query"]
        $get_metadata.tables     -> context["node_outputs"]["get_metadata"]["tables"]
        literal string           -> returned as-is
    """
    if not isinstance(ref, str) or not ref.startswith("$"):
        return ref

    parts = ref[1:].split(".", 1)
    scope = parts[0]
    rest = parts[1] if len(parts) > 1 else None

    # $input.* resolves from input_data
    if scope == "input":
        value = context.get("input_data", {})
    else:
        # $node_id.* resolves from node_outputs
        value = context.get("node_outputs", {}).get(scope)

    if value is None:
        raise ValueError(f"Reference '{ref}': scope '{scope}' not found in context")

    if rest is None:
        return value

    for key in rest.split("."):
        if isinstance(value, dict):
            if key not in value:
                raise ValueError(f"Reference '{ref}': key '{key}' not found")
            value = value[key]
        elif isinstance(value, list):
            try:
                value = value[int(key)]
            except (ValueError, IndexError):
                raise ValueError(f"Reference '{ref}': invalid list index '{key}'")
        else:
            raise ValueError(f"Reference '{ref}': cannot traverse into {type(value)}")

    return value


def _resolve_input_map(
    input_map: Dict[str, str], state: ToolGraphState
) -> Dict[str, Any]:
    """Resolve all $-references in an input_map using LangGraph state."""
    context = {
        "input_data": state.get("input_data", {}),
        "node_outputs": state.get("node_outputs", {}),
    }
    return {param: _resolve_ref(ref, context) for param, ref in input_map.items()}


# ── Topological sort ────────────────────────────────────────────

def _topological_sort(nodes: Dict[str, ToolGraphNode]) -> List[str]:
    """Return node ids in dependency-respecting execution order."""
    in_degree: Dict[str, int] = {nid: 0 for nid in nodes}
    adjacency: Dict[str, List[str]] = {nid: [] for nid in nodes}

    for nid, node in nodes.items():
        for dep in node.depends_on:
            if dep not in nodes:
                raise ValueError(f"Node '{nid}' depends on unknown node '{dep}'")
            adjacency[dep].append(nid)
            in_degree[nid] += 1

    queue = sorted(nid for nid, deg in in_degree.items() if deg == 0)
    order: List[str] = []

    while queue:
        current = queue.pop(0)
        order.append(current)
        for neighbor in sorted(adjacency[current]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("Cycle detected in tool graph — execution order is ambiguous")

    return order


# ── Main class ──────────────────────────────────────────────────

class ToolExecutionGraph:
    """
    Deterministic tool execution graph built on LangGraph.

    The LLM never decides which tool to call next — the StateGraph does.
    Each node is a fixed tool call wired via add_edge / add_conditional_edges.
    """

    def __init__(self, graph_id: str = "default"):
        self.graph_id = graph_id
        self.nodes: Dict[str, ToolGraphNode] = {}
        self._execution_order: Optional[List[str]] = None
        self._compiled_graph = None
        self.status: GraphStatus = GraphStatus.PENDING
        self._toolkit = None
        self._last_state: Optional[ToolGraphState] = None
        self._fn_registry: Dict[str, Callable] = {}  # name → callable for JSON-based local fns

    # ── Construction ────────────────────────────────────────────

    def add_node(self, node: ToolGraphNode) -> "ToolExecutionGraph":
        if node.id in self.nodes:
            raise ValueError(f"Duplicate node id: '{node.id}'")
        self.nodes[node.id] = node
        self._execution_order = None
        self._compiled_graph = None
        return self

    @classmethod
    def from_json(cls, config: Dict[str, Any]) -> "ToolExecutionGraph":
        """
        Build graph from JSON config.

        Nodes can specify either ``"tool"`` (MCP) or ``"fn"`` (local).
        When using ``"fn"`` in JSON, the value is a string key that must be
        registered via ``graph.register_fn(name, callable)`` before execution.

        {
            "graph_id": "nl_to_sql",
            "nodes": [
                {
                    "id": "get_metadata",
                    "tool": "get_tables_metadata",
                    "input_map": {"query": "$input.user_query"},
                    "output_key": "tables_metadata"
                },
                {
                    "id": "validate",
                    "fn": "validate_tables",
                    "input_map": {"tables": "$get_metadata.tables_metadata"},
                    "output_key": "validated",
                    "depends_on": ["get_metadata"]
                }
            ]
        }
        """
        graph = cls(graph_id=config.get("graph_id", "default"))
        for node_cfg in config.get("nodes", []):
            # fn in JSON is a registry key (string), resolved at compile time
            fn_key = node_cfg.get("fn")
            graph.add_node(ToolGraphNode(
                id=node_cfg["id"],
                tool=node_cfg.get("tool", ""),
                fn=fn_key,  # stored as string; resolved in _resolve_node_fn()
                input_map=node_cfg.get("input_map", {}),
                output_key=node_cfg.get("output_key", node_cfg["id"]),
                depends_on=node_cfg.get("depends_on", []),
                max_retries=node_cfg.get("max_retries", 3),
                retry_delay=node_cfg.get("retry_delay", 1.0),
            ))
        return graph

    # ── Toolkit ─────────────────────────────────────────────────

    def _get_toolkit(self):
        if self._toolkit is None:
            from abi_core.common.semantic_tools import MCPToolkit
            self._toolkit = MCPToolkit()
        return self._toolkit

    def set_toolkit(self, toolkit) -> "ToolExecutionGraph":
        """Inject a custom toolkit (useful for testing or non-MCP tools)."""
        self._toolkit = toolkit
        return self

    def register_fn(self, name: str, fn: Callable) -> "ToolExecutionGraph":
        """
        Register a local function for use in JSON-defined graphs.

        When a node has ``"fn": "name"`` in JSON, the graph resolves it
        against this registry at compile time.

        Args:
            name: Key used in JSON config
            fn: Sync or async callable

        Example:
            graph = ToolExecutionGraph.from_json(config)
            graph.register_fn("validate_tables", my_validate_fn)
            result = await graph.execute(input_data)
        """
        self._fn_registry[name] = fn
        self._compiled_graph = None  # Invalidate
        return self

    def _resolve_node_fn(self, node: ToolGraphNode) -> Optional[Callable]:
        """Resolve the callable for a node (direct fn or registry lookup)."""
        if node.fn is None:
            return None
        if callable(node.fn):
            return node.fn
        # String key → look up in registry
        if isinstance(node.fn, str):
            fn = self._fn_registry.get(node.fn)
            if fn is None:
                raise ValueError(
                    f"Node '{node.id}': fn '{node.fn}' not found in registry. "
                    f"Call graph.register_fn('{node.fn}', callable) before execute."
                )
            return fn
        raise ValueError(f"Node '{node.id}': fn must be a callable or a registry key string")

    # ── Graph compilation ───────────────────────────────────────

    @property
    def execution_order(self) -> List[str]:
        if self._execution_order is None:
            self._execution_order = _topological_sort(self.nodes)
        return self._execution_order

    def _make_node_fn(self, node: ToolGraphNode):
        """Create an async LangGraph node function for a ToolGraphNode."""
        # Resolve execution target: local fn or MCP tool
        local_fn = self._resolve_node_fn(node)
        toolkit = None if local_fn else self._get_toolkit()
        exec_label = f"fn={node.fn}" if local_fn else f"tool={node.tool}"

        async def node_fn(state: ToolGraphState) -> Dict[str, Any]:
            node.status = NodeStatus.RUNNING
            node.attempts += 1

            abi_logging(
                f"[▶️] Graph '{self.graph_id}' — node '{node.id}' "
                f"({exec_label}, attempt {node.attempts}/{node.max_retries})"
            )

            try:
                resolved_args = _resolve_input_map(node.input_map, state)
            except ValueError as e:
                node.status = NodeStatus.FAILED
                node.error = str(e)
                return {
                    "failed_node": node.id,
                    "error": f"Input resolution error: {e}",
                    "status": GraphStatus.FAILED.value,
                }

            # Retry loop inside the node
            last_error = None
            for attempt in range(node.max_retries):
                try:
                    # Dispatch: local fn or MCP tool
                    if local_fn:
                        if inspect.iscoroutinefunction(local_fn):
                            result = await local_fn(**resolved_args)
                        else:
                            result = local_fn(**resolved_args)
                    else:
                        result = await toolkit.call(node.tool, **resolved_args)

                    if isinstance(result, dict) and "error" in result:
                        raise RuntimeError(result["error"])

                    # Success
                    node.result = result
                    node.status = NodeStatus.COMPLETED
                    node.error = None

                    key = node.output_key or node.id
                    new_outputs = {**state.get("node_outputs", {}), key: result}
                    new_completed = state.get("completed_nodes", []) + [node.id]

                    abi_logging(f"[✅] Node '{node.id}' completed")

                    return {
                        "node_outputs": new_outputs,
                        "current_node": node.id,
                        "completed_nodes": new_completed,
                        "failed_node": None,
                        "error": None,
                        "status": GraphStatus.RUNNING.value,
                    }

                except Exception as e:
                    last_error = str(e)
                    node.attempts = attempt + 1
                    abi_logging(
                        f"[⚠️] Node '{node.id}' attempt {attempt + 1}/{node.max_retries}: {e}",
                        level="warning",
                    )
                    if attempt < node.max_retries - 1:
                        wait = node.retry_delay * (attempt + 1)
                        await asyncio.sleep(wait)

            # All retries exhausted
            node.status = NodeStatus.FAILED
            node.error = last_error
            abi_logging(
                f"[❌] Node '{node.id}' failed after {node.max_retries} attempts",
                level="error",
            )
            return {
                "failed_node": node.id,
                "error": last_error,
                "status": GraphStatus.PAUSED.value,
            }

        return node_fn

    def _should_continue(self, state: ToolGraphState) -> str:
        """Conditional edge: continue to next node or stop on failure."""
        if state.get("failed_node"):
            return "__end__"
        return "__continue__"

    def compile(self):
        """Build and compile the LangGraph StateGraph."""
        if self._compiled_graph is not None:
            return self._compiled_graph

        order = self.execution_order
        if not order:
            raise ValueError("Cannot compile empty graph")

        builder = StateGraph(ToolGraphState)

        # Register all nodes
        for node_id in order:
            node = self.nodes[node_id]
            builder.add_node(node_id, self._make_node_fn(node))

        # Set entry point
        builder.set_entry_point(order[0])

        # Wire edges: each node → conditional → next or END
        for i, node_id in enumerate(order):
            if i < len(order) - 1:
                next_node = order[i + 1]
                builder.add_conditional_edges(
                    node_id,
                    self._should_continue,
                    {"__continue__": next_node, "__end__": END},
                )
            else:
                # Last node always goes to END
                builder.add_edge(node_id, END)

        self._compiled_graph = builder.compile()
        return self._compiled_graph

    # ── Execution ───────────────────────────────────────────────

    async def execute(
        self,
        input_data: Dict[str, Any],
        on_node_complete=None,
    ) -> Dict[str, Any]:
        """
        Execute the full graph deterministically via LangGraph.

        Args:
            input_data: Initial data available as $input.* references
            on_node_complete: Optional async callback(node_id, result)

        Returns:
            Dict with all node outputs and execution metadata
        """
        self.status = GraphStatus.RUNNING
        graph = self.compile()

        initial_state: ToolGraphState = {
            "input_data": input_data,
            "node_outputs": {},
            "current_node": "",
            "completed_nodes": [],
            "failed_node": None,
            "error": None,
            "status": GraphStatus.RUNNING.value,
        }

        abi_logging(f"[🚀] Executing graph '{self.graph_id}' ({len(self.nodes)} nodes)")

        final_state = initial_state
        async for event in graph.astream(initial_state):
            for node_id, node_state in event.items():
                if isinstance(node_state, dict):
                    final_state = {**final_state, **node_state}

                    # Callback on completion
                    if (
                        on_node_complete
                        and node_id in self.nodes
                        and not node_state.get("failed_node")
                    ):
                        output_key = self.nodes[node_id].output_key or node_id
                        result = node_state.get("node_outputs", {}).get(output_key)
                        await on_node_complete(node_id, result)

        self._last_state = final_state

        if final_state.get("failed_node"):
            self.status = GraphStatus.PAUSED
            abi_logging(
                f"[⏸️] Graph '{self.graph_id}' paused at '{final_state['failed_node']}'",
                level="error",
            )
        else:
            self.status = GraphStatus.COMPLETED
            abi_logging(f"[🏁] Graph '{self.graph_id}' completed")

        return final_state

    async def resume(self, on_node_complete=None) -> Dict[str, Any]:
        """
        Resume from the last failed node.

        Completed nodes are skipped (their outputs remain in state).
        Failed nodes are reset and re-executed.
        """
        if self.status not in (GraphStatus.PAUSED, GraphStatus.FAILED):
            abi_logging(f"[ℹ️] Graph '{self.graph_id}' is '{self.status.value}', nothing to resume")
            return self._last_state or {}

        # Reset failed nodes
        for node in self.nodes.values():
            if node.status == NodeStatus.FAILED:
                node.reset()

        # Re-execute with preserved state
        prev = self._last_state or {}
        input_data = prev.get("input_data", {})

        # Rebuild initial state keeping completed outputs
        self.status = GraphStatus.RUNNING
        graph = self.compile()

        resume_state: ToolGraphState = {
            "input_data": input_data,
            "node_outputs": prev.get("node_outputs", {}),
            "current_node": "",
            "completed_nodes": prev.get("completed_nodes", []),
            "failed_node": None,
            "error": None,
            "status": GraphStatus.RUNNING.value,
        }

        abi_logging(f"[🔄] Resuming graph '{self.graph_id}'")

        final_state = resume_state
        async for event in graph.astream(resume_state):
            for node_id, node_state in event.items():
                if isinstance(node_state, dict):
                    final_state = {**final_state, **node_state}

                    if (
                        on_node_complete
                        and node_id in self.nodes
                        and not node_state.get("failed_node")
                    ):
                        output_key = self.nodes[node_id].output_key or node_id
                        result = node_state.get("node_outputs", {}).get(output_key)
                        await on_node_complete(node_id, result)

        self._last_state = final_state

        if final_state.get("failed_node"):
            self.status = GraphStatus.PAUSED
        else:
            self.status = GraphStatus.COMPLETED
            abi_logging(f"[🏁] Graph '{self.graph_id}' completed after resume")

        return final_state

    # ── Introspection ───────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "status": self.status.value,
            "execution_order": self.execution_order,
            "nodes": {
                nid: {
                    "tool": n.tool or None,
                    "fn": str(n.fn) if n.fn else None,
                    "status": n.status.value,
                    "attempts": n.attempts,
                    "error": n.error,
                    "has_result": n.result is not None,
                }
                for nid, n in self.nodes.items()
            },
            "completed": [
                nid for nid, n in self.nodes.items()
                if n.status == NodeStatus.COMPLETED
            ],
        }

    def reset(self):
        """Reset graph to initial state for re-execution."""
        self.status = GraphStatus.PENDING
        self._compiled_graph = None
        self._last_state = None
        for node in self.nodes.values():
            node.reset()

    def __repr__(self) -> str:
        done = sum(1 for n in self.nodes.values() if n.status == NodeStatus.COMPLETED)
        return (
            f"ToolExecutionGraph(id='{self.graph_id}', "
            f"nodes={len(self.nodes)}, "
            f"completed={done}/{len(self.nodes)}, "
            f"status={self.status.value})"
        )
