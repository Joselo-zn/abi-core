"""
Tool Enforcement — Track and enforce tool usage in steps.

When a step declares tools=["write_file"], this module:
1. Wraps the tools to track which ones were called
2. After execution, checks if required tools were used
3. If not, provides retry prompt and deterministic fallback
"""

import re
from typing import Any, Dict, List, Optional
from copy import deepcopy

from langchain_core.tools import BaseTool

from abi_core.common.utils import abi_logging


class ToolTracker:
    """Wraps tools to track executions and enforce usage."""

    def __init__(self, tools: List[BaseTool], required_tool_names: List[str]):
        self.required = required_tool_names
        self.executions: List[Dict[str, Any]] = []
        self.wrapped_tools = self._wrap_all(tools)
        self._tools_by_name = {t.name: t for t in tools}

    def _wrap_all(self, tools: List[BaseTool]) -> List[BaseTool]:
        """Wrap each tool to record executions."""
        wrapped = []
        for tool in tools:
            wrapped.append(self._wrap_tool(tool))
        return wrapped

    def _wrap_tool(self, tool: BaseTool) -> BaseTool:
        """Create a tracked version of a tool."""
        tracker = self
        original_func = tool.func

        def tracked_func(*args, **kwargs):
            result = original_func(*args, **kwargs)
            tracker.executions.append({
                "tool": tool.name,
                "args": kwargs,
                "result": str(result),
            })
            abi_logging(f"[🔧 Tracker] Tool '{tool.name}' executed")
            return result

        # Create a copy with the tracked function
        tracked_tool = deepcopy(tool)
        tracked_tool.func = tracked_func
        return tracked_tool

    def get_missing(self) -> List[str]:
        """Return required tools that were NOT called."""
        called = {e["tool"] for e in self.executions}
        return [t for t in self.required if t not in called]

    def get_enforcement_prompt(self, llm_result: str) -> str:
        """Generate a retry prompt for tools that weren't used."""
        missing = self.get_missing()
        tools_desc = ", ".join(missing)
        return (
            f"You were required to use these tools but did NOT call them: {tools_desc}\n\n"
            f"Your previous output was:\n{llm_result[:3000]}\n\n"
            f"NOW you MUST call {missing[0]} with the appropriate arguments.\n"
            f"Do not explain. Do not describe. Just call the tool."
        )

    def execute_fallback(self, llm_result: str) -> List[Dict[str, Any]]:
        """Deterministic fallback: extract params from LLM output and call tools directly.

        Returns list of execution results.
        """
        results = []

        for tool_name in self.get_missing():
            tool = self._tools_by_name.get(tool_name)
            if not tool:
                continue

            args = self._extract_args_for_tool(tool_name, llm_result)
            if args:
                try:
                    result = tool.func(**args)
                    self.executions.append({
                        "tool": tool_name,
                        "args": args,
                        "result": str(result),
                        "source": "fallback",
                    })
                    abi_logging(f"[🔧 Fallback] Executed '{tool_name}' programmatically")
                    results.append({"tool": tool_name, "result": result})
                except Exception as e:
                    abi_logging(f"[❌ Fallback] Failed to execute '{tool_name}': {e}")
            else:
                abi_logging(f"[⚠️ Fallback] Could not extract args for '{tool_name}'")

        return results

    def _extract_args_for_tool(self, tool_name: str, llm_result: str) -> Optional[Dict[str, Any]]:
        """Extract tool arguments from LLM text output.

        Generic extraction strategies based on tool parameter names.
        """
        tool = self._tools_by_name.get(tool_name)
        if not tool:
            return None

        # Get the tool's expected parameters from its schema
        schema = tool.args_schema.schema() if hasattr(tool, 'args_schema') and tool.args_schema else {}
        properties = schema.get("properties", {})
        param_names = list(properties.keys())

        # Strategy: extract based on known parameter patterns
        args = {}

        if "filename" in param_names:
            args["filename"] = self._extract_filename(llm_result)

        if "content" in param_names:
            args["content"] = self._extract_code_content(llm_result)

        if "command" in param_names:
            args["command"] = self._extract_command(llm_result)

        # Only return if we have all required params with values
        if args and all(v for v in args.values()):
            return args

        return None

    @staticmethod
    def _extract_filename(text: str) -> str:
        """Extract filename from text (e.g. 'named pong.py' or 'file main.py')."""
        match = re.search(r'named\s+[`"\']?(\S+\.\w+)[`"\']?', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'file\s+[`"\']?(\S+\.\w+)[`"\']?', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'`(\w+\.\w+)`', text)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def _extract_code_content(text: str) -> str:
        """Extract code from markdown code blocks."""
        blocks = re.findall(r'```(?:\w*)\n(.*?)```', text, re.DOTALL)
        if blocks:
            return "\n\n".join(blocks)
        return ""

    @staticmethod
    def _extract_command(text: str) -> str:
        """Extract shell command from text."""
        match = re.search(r'```(?:sh|bash|shell)\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'^\$\s+(.+)$', text, re.MULTILINE)
        if match:
            return match.group(1)
        return ""


def get_enforcement_system_prompt(required_tools: List[str]) -> str:
    """Generate system prompt addition that reminds the LLM to use tools."""
    tools_str = ", ".join(required_tools)
    return (
        f"\n\nMANDATORY TOOL USAGE: You MUST call these tools during this task: {tools_str}. "
        f"Do NOT just describe what you would do. Actually CALL the tools. "
        f"If you need to write a file, call write_file. If you need to run a command, call run_shell. "
        f"Your response is INCOMPLETE unless you have called the required tools."
    )
