"""
abi_core.agent.agent_response — Streaming response helpers for @agent.task.

Usage inside a task:
    from abi_core.agent.agent_response import AgentResponse

    @agent.task(name="my_task", task_id="task-001")
    async def my_task(query):
        yield AgentResponse.status("Processing...")
        result = await agent.execute_step("my_step", query=query)
        yield AgentResponse.result(result)
"""

from __future__ import annotations

from typing import Any


class AgentResponse:
    """Factory for streaming response dicts from @agent.task functions."""

    @staticmethod
    def status(message: str, *args, **kwargs) -> dict:
        """Emit a status update — visible to the client but not a final result."""
        return {
            "response_type": "status",
            "content": message,
            "is_task_completed": False,
            "require_user_input": False,
            "meta": kwargs,
        }

    @staticmethod
    def result(data: Any) -> dict:
        """Emit the final result of the task."""
        return {
            "response_type": "data",
            "content": data,
            "is_task_completed": True,
            "require_user_input": False,
        }

    @staticmethod
    def text(message: str) -> dict:
        """Emit a text response — final, human-readable."""
        return {
            "response_type": "text",
            "content": message,
            "is_task_completed": True,
            "require_user_input": False,
        }

    @staticmethod
    def error(message: str) -> dict:
        """Emit an error response."""
        return {
            "response_type": "error",
            "content": message,
            "is_task_completed": True,
            "require_user_input": False,
        }

    @staticmethod
    def input_required(prompt: str) -> dict:
        """Pause execution and ask the user for input."""
        return {
            "response_type": "input_required",
            "content": prompt,
            "is_task_completed": False,
            "require_user_input": True,
        }
