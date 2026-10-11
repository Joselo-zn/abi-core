"""
Prompts any agent can reach: the generated agents' role prompt, required-
tool enforcement, and the LLM turn after a DAG.

Spec: .abi/specs/implemented/prompts-single-location.md
"""

from typing import List


WORKER_PROMPT = """
You are an execution agent responsible for completing a clearly defined task as assigned by the Orchestrator or Planner. Your objective is to execute with precision, traceability, and transparency. You are not expected to evaluate the task or question its logic — only to complete it faithfully, logging each step clearly.
"""


def get_enforcement_system_prompt(required_tools: List[str]) -> str:
    """Generate system prompt addition that reminds the LLM to use tools."""
    tools_str = ", ".join(required_tools)
    return (
        f"\n\nMANDATORY TOOL USAGE: You MUST call these tools during this task: {tools_str}. "
        f"Do NOT just describe what you would do. Actually CALL the tools. "
        f"If you need to write a file, call write_file. If you need to run a command, call run_shell. "
        f"Your response is INCOMPLETE unless you have called the required tools."
    )


def build_enforcement_retry_prompt(missing: List[str], llm_result: str) -> str:
    """Retry message for required tools the model did not call."""
    tools_desc = ", ".join(missing)
    return (
        f"You were required to use these tools but did NOT call them: {tools_desc}\n\n"
        f"Your previous output was:\n{llm_result[:3000]}\n\n"
        f"NOW you MUST call {missing[0]} with the appropriate arguments.\n"
        f"Do not explain. Do not describe. Just call the tool."
    )


ENFORCEMENT_RETRY_SYSTEM_PROMPT = "You MUST call the required tools. Do not explain. Just call them."


def build_pipeline_result_query(dag_summary: str, query: str) -> str:
    """The LLM turn after an agent's DAG, when it has standalone tools."""
    return f"[Pipeline result]: {dag_summary}\n\nOriginal request: {query}"
