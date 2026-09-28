"""
Planner-specific prompt content.

Loose prompt strings that used to live inline inside planner.py's methods,
consolidated here so every piece of text the planner sends to an LLM lives
in one place. This sits alongside — not duplicating —
abi_core.common.prompts.PLANNER_COT_INSTRUCTIONS (the framework-shared
system prompt used to construct the agent itself and to decompose a query);
that one stays in the shared framework file since other code may reuse it.
Everything here is specific to this agent's own direct_tool content
generation.

config.py imports this module and exposes everything through `config.*`, so
planner.py never imports prompt content directly — it only reads config.
"""

import json


def build_planning_query(query: str, context: dict) -> str:
    """The human-turn prompt for the planning DAG's LLM decomposition call
    — the raw user request plus session context."""
    return f"User request: {query}\nContext: {json.dumps(context, indent=2)}"


def build_direct_tool_content_prompt(description: str) -> str:
    """Prompt asking the LLM to write the actual content for a direct_tool
    deliverable (e.g. write_pdf) from its short task description — plain
    completion, no tools, no agentic loop; the code (not the model) decides
    which tool to call with the result. See
    .abi/specs/implemented/planner-direct-tool-pdf.md."""
    return (
        f"Write the full content for this deliverable:\n\n{description}\n\n"
        f"Respond with ONLY the content itself — no preamble, no markdown code fences."
    )
