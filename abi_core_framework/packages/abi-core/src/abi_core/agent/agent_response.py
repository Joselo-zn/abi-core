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
    def element(element_type: str, props: dict, name: str | None = None, *args, **kwargs) -> dict:
        """Emit a rich element (image, file, dataframe, qr, a custom .jsx
        name, ...) to render alongside the response.

        A turn may emit zero, one, or several of these before its final
        response (text/result) — the renderer collects them and attaches
        them to the message they belong with, the same way Chainlit expects
        (``cl.Message(content=..., elements=[...])``) rather than treating
        each element as a standalone response on its own. See
        .abi/specs/agent-rich-elements.md.

        Args:
            element_type: One of the built-in renderer types ("image",
                "file", "pdf", "audio", "video", "text", "dataframe", "qr")
                or the name of a custom .jsx element (see
                .abi/specs/agent-custom-elements.md).
            props: Type-specific payload. For url-based types (image, file,
                pdf, audio, video), prefer a "url" prop pointing at an
                already-uploaded artifact (e.g. via ArtifactStore.get_url())
                over inlining large binary content in this message.
            name: Display name for the element. Defaults to element_type.
        """
        return {
            "response_type": "element",
            "content": {"element_type": element_type, "name": name or element_type, "props": props},
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
    def input_required(prompt: str, *args, **kwargs) -> dict:
        """Pause execution and ask the user for input.

        Extra keyword arguments (e.g. ``status``, ``questions``) are preserved
        under ``meta`` for clients that render structured clarification, but
        are not required by the executor (which only reads ``content`` and
        ``require_user_input``).
        """
        return {
            "response_type": "input_required",
            "content": prompt,
            "is_task_completed": False,
            "require_user_input": True,
            "meta": kwargs,
        }
