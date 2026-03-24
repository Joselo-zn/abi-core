"""
Example: Deterministic NL-to-SQL pipeline using ToolExecutionGraph (LangGraph)

Demonstrates three execution modes:
- MCP tool calls (remote)
- Local functions (sync/async)
- Mixed: local validation between MCP calls

The graph enforces strict order regardless of LLM reasoning.
"""

import asyncio
from abi_core.common.tool_graph import ToolExecutionGraph, ToolGraphNode


# ── Local functions (no MCP needed) ────────────────────────────

def validate_tables(tables_metadata: dict) -> dict:
    """Local sync function: validate that metadata contains usable tables."""
    tables = tables_metadata.get("tables", [])
    if not tables:
        raise ValueError("No tables found matching the query")
    return {
        "valid": True,
        "table_count": len(tables),
        "tables": tables,
    }


async def format_result(query_result: dict, user_query: str) -> dict:
    """Local async function: format the final SQL result."""
    return {
        "original_query": user_query,
        "sql": query_result.get("sql", ""),
        "rows": query_result.get("rows", []),
        "row_count": len(query_result.get("rows", [])),
    }


# ── Option A: Programmatic with local fn ───────────────────────

async def example_with_local_fn():
    """Mix MCP tools and local functions in the same graph."""
    print("=" * 60)
    print("NL-to-SQL with local validation (programmatic)")
    print("=" * 60)

    graph = ToolExecutionGraph(graph_id="nl_to_sql_validated")

    # Step 1: MCP tool — get table metadata
    graph.add_node(ToolGraphNode(
        id="get_metadata",
        tool="get_tables_metadata",
        input_map={"query": "$input.user_query"},
        output_key="tables_metadata",
    ))

    # Step 2: LOCAL function — validate tables exist
    graph.add_node(ToolGraphNode(
        id="validate",
        fn=validate_tables,
        input_map={"tables_metadata": "$get_metadata.tables_metadata"},
        output_key="validated",
        depends_on=["get_metadata"],
        max_retries=1,  # No point retrying a validation
    ))

    # Step 3: MCP tool — get sample data
    graph.add_node(ToolGraphNode(
        id="get_samples",
        tool="get_sample_data",
        input_map={"tables": "$validated.tables"},
        output_key="sample_data",
        depends_on=["validate"],
    ))

    # Step 4: MCP tool — create SQL query
    graph.add_node(ToolGraphNode(
        id="create_query",
        tool="create_sql_query",
        input_map={
            "user_query": "$input.user_query",
            "tables": "$validated.tables",
            "samples": "$get_samples.sample_data",
        },
        output_key="query_result",
        depends_on=["get_samples"],
    ))

    # Step 5: LOCAL async function — format result
    graph.add_node(ToolGraphNode(
        id="format",
        fn=format_result,
        input_map={
            "query_result": "$create_query.query_result",
            "user_query": "$input.user_query",
        },
        output_key="final_result",
        depends_on=["create_query"],
        max_retries=1,
    ))

    print(f"\n📋 Order: {graph.execution_order}")
    result = await graph.execute({"user_query": "ventas por región Q4 2024"})
    print(f"📊 Status: {graph.status.value}")


# ── Option B: JSON config + registered functions ───────────────

NL_TO_SQL_CONFIG = {
    "graph_id": "nl_to_sql_json",
    "nodes": [
        {
            "id": "get_metadata",
            "tool": "get_tables_metadata",
            "input_map": {"query": "$input.user_query"},
            "output_key": "tables_metadata",
        },
        {
            "id": "validate",
            "fn": "validate_tables",
            "input_map": {"tables_metadata": "$get_metadata.tables_metadata"},
            "output_key": "validated",
            "depends_on": ["get_metadata"],
            "max_retries": 1,
        },
        {
            "id": "get_samples",
            "tool": "get_sample_data",
            "input_map": {"tables": "$validated.tables"},
            "output_key": "sample_data",
            "depends_on": ["validate"],
        },
        {
            "id": "create_query",
            "tool": "create_sql_query",
            "input_map": {
                "user_query": "$input.user_query",
                "tables": "$validated.tables",
                "samples": "$get_samples.sample_data",
            },
            "output_key": "query_result",
            "depends_on": ["get_samples"],
        },
    ],
}


async def example_json_with_registry():
    """Build from JSON, register local functions before execution."""
    print("\n" + "=" * 60)
    print("NL-to-SQL from JSON + function registry")
    print("=" * 60)

    graph = ToolExecutionGraph.from_json(NL_TO_SQL_CONFIG)

    # Register local functions referenced by name in JSON
    graph.register_fn("validate_tables", validate_tables)

    print(f"\n📋 Order: {graph.execution_order}")
    result = await graph.execute({"user_query": "top 10 clientes"})
    print(f"📊 Status: {graph.status.value}")


# ── Option C: Pure local (no MCP, great for testing) ───────────

async def example_pure_local():
    """All nodes are local functions — no MCP server needed."""
    print("\n" + "=" * 60)
    print("Pure local graph (no MCP)")
    print("=" * 60)

    def step_a(text: str) -> dict:
        return {"upper": text.upper(), "length": len(text)}

    async def step_b(upper: str, length: int) -> dict:
        return {"message": f"Processed '{upper}' ({length} chars)"}

    graph = ToolExecutionGraph(graph_id="local_test")

    graph.add_node(ToolGraphNode(
        id="transform",
        fn=step_a,
        input_map={"text": "$input.text"},
        output_key="transformed",
    ))
    graph.add_node(ToolGraphNode(
        id="summarize",
        fn=step_b,
        input_map={
            "upper": "$transformed.upper",
            "length": "$transformed.length",
        },
        output_key="summary",
        depends_on=["transform"],
    ))

    result = await graph.execute({"text": "hello world"})

    print(f"📊 Status: {graph.status.value}")
    print(f"📦 Output: {result['node_outputs'].get('summary')}")


if __name__ == "__main__":
    asyncio.run(example_pure_local())
    asyncio.run(example_with_local_fn())
    asyncio.run(example_json_with_registry())
