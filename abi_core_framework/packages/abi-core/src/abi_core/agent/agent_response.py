"""
AgentResponse — Structured response object for ABI agents.

Replaces raw dicts in yield statements with a typed, serializable object
that has factory methods for common response patterns.

Usage:
    yield AgentResponse.success("Here is the answer", agent="planner", task_id="t1")
    yield AgentResponse.error("Something broke", agent="planner")
    yield AgentResponse.empty()
    yield AgentResponse.input_required("What dataset?", agent="planner")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentResponse:
    """Structured agent response with serialization support.

    Attributes:
        content: The response text or data.
        response_type: 'text' or 'data'.
        is_task_completed: Whether the task finished.
        require_user_input: Whether the agent needs more info from the user.
        metadata: Arbitrary key-value pairs (agent, model, context_id, etc.).
    """

    content: str
    response_type: str = "text"
    is_task_completed: bool = True
    require_user_input: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory methods ─────────────────────────────────────────

    @classmethod
    def success(cls, content: str, **metadata) -> "AgentResponse":
        """Task completed successfully."""
        return cls(
            content=content,
            response_type="text",
            is_task_completed=True,
            require_user_input=False,
            metadata=metadata,
        )

    @classmethod
    def error(cls, content: str, **metadata) -> "AgentResponse":
        """Task completed with an error."""
        return cls(
            content=content,
            response_type="text",
            is_task_completed=True,
            require_user_input=False,
            metadata={"error": content, **metadata},
        )

    @classmethod
    def empty(cls) -> "AgentResponse":
        """No response generated."""
        return cls(
            content="No response generated from agent",
            response_type="text",
            is_task_completed=True,
            require_user_input=False,
        )

    @classmethod
    def input_required(cls, content: str, **metadata) -> "AgentResponse":
        """Agent needs more information from the user."""
        return cls(
            content=content,
            response_type="text",
            is_task_completed=False,
            require_user_input=True,
            metadata=metadata,
        )

    @classmethod
    def status(cls, content: str, **metadata) -> "AgentResponse":
        """Intermediate status / heartbeat while the agent is still working.

        Keeps SSE connections alive through proxies (e.g. CloudFront 30s timeout).
        Consumers should treat these as progress updates, not final results.
        """
        return cls(
            content=content,
            response_type="status",
            is_task_completed=False,
            require_user_input=False,
            metadata=metadata,
        )

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (compatible with existing consumers)."""
        d: Dict[str, Any] = {
            "content": self.content,
            "response_type": self.response_type,
            "is_task_completed": self.is_task_completed,
            "require_user_input": self.require_user_input,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    # Allow dict-style access so existing code like chunk.get('content') works
    def get(self, key: str, default: Any = None) -> Any:
        """Dict-compatible get() for backward compatibility."""
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()
