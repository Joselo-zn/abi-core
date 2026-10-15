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

from enum import Enum
from typing import Any, Optional


class RunPhase(str, Enum):
    """Closed set of run phases a status update can declare via ``phase=``.

    Clients (e.g. abi_core.ui.chainlit_app) map these to human-readable,
    localized labels — the free-text ``message`` stays for logs and for
    clients that don't understand phases. Pass ``.value`` so ``meta`` stays
    plain JSON. See
    .abi/specs/not-implemented/ux/chainlit-run-progress-indicator.md.
    """

    ANALYZING = "analyzing"
    ROUTING = "routing"
    PLANNING = "planning"
    BUILDING = "building"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"


class AgentResponse:
    """Factory for streaming response dicts from @agent.task functions."""

    @staticmethod
    def status(message: str, *args, **kwargs) -> dict:
        """Emit a status update — visible to the client but not a final result.

        Every keyword argument lands in ``meta`` unchanged. Keys with a known
        meaning to the bundled Chainlit UI (all optional):

        - ``phase``: a ``RunPhase`` value — which stage of the run this is.
        - ``phase_detail``: short free text shown under the active phase/step.
        - ``task_key`` / ``task_label``: the plan task this update belongs to.
        - ``task_index`` / ``task_total``: 1-based position of that task.
        - ``agent``: the agent that produced the update.
        """
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
    def error(message: str, code: Optional[str] = None, **meta) -> dict:
        """Emit an error response. ``code`` (e.g. "timeout") goes in
        ``meta.error_code`` so a client can show its own, localized text;
        ``message`` is the English text for everyone else."""
        response = {
            "response_type": "error",
            "content": message,
            "is_task_completed": True,
            "require_user_input": False,
        }
        if code:
            response["meta"] = {"error_code": code, **meta}
        return response

    @staticmethod
    def error_from(exc: BaseException) -> dict:
        """Error response for an exception, with its ``error_code`` (and
        ``max_wait``) when the exception declares one, like
        HeartbeatTimeoutError."""
        code = getattr(exc, "error_code", None)
        extra = {"max_wait": int(exc.max_wait)} if getattr(exc, "max_wait", None) else {}
        return AgentResponse.error(str(exc), code, **extra)

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
