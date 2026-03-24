"""
A2AResponse — Clean wrapper for raw A2A streaming results.

Encapsulates the deeply nested ``hasattr`` chains required to navigate
A2A protocol objects (SendMessageSuccessResponse, Task, Artifact, Part,
TaskStatus, etc.) into a simple, pythonic interface.

Usage:
    results = []
    async for chunk in workflow.run_workflow():
        results.append(chunk)

    for resp in A2AResponse.from_results(results):
        if resp.is_input_required:
            print(f"Agent needs info: {resp.status_message}")
        elif resp.data and "tasks" in resp.data:
            print(f"Got plan with {len(resp.data['tasks'])} tasks")
        elif resp.text:
            print(f"Text response: {resp.text}")
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _safe_get(obj, *attrs):
    """Walk a chain of attributes, returning None if any is missing."""
    for attr in attrs:
        if obj is None:
            return None
        obj = getattr(obj, attr, None)
    return obj


@dataclass
class A2AResponse:
    """Parsed view of a single A2A streaming result.

    Attributes:
        state: Task state string (e.g. "completed", "input-required").
        text: First text content found in artifacts or status message.
        data: First dict/data content found in artifacts.
        artifacts_raw: Raw artifact objects for advanced access.
        status_message: Text from ``task.status.message`` (clarifications, etc.).
        raw: The original unparsed result object.
    """

    state: Optional[str] = None
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    artifacts_raw: List[Any] = field(default_factory=list)
    status_message: Optional[str] = None
    raw: Any = None

    # ── Convenience properties ──────────────────────────────────

    @property
    def is_input_required(self) -> bool:
        """True when the remote agent is asking for more information."""
        if not self.state:
            return False
        s = str(self.state).lower()
        return "input" in s and "required" in s

    @property
    def is_completed(self) -> bool:
        s = str(self.state).lower() if self.state else ""
        return "completed" in s

    @property
    def is_failed(self) -> bool:
        s = str(self.state).lower() if self.state else ""
        return "failed" in s

    # ── Factory ─────────────────────────────────────────────────

    @classmethod
    def parse(cls, result) -> "A2AResponse":
        """Parse a single raw A2A streaming result into an A2AResponse."""
        resp = cls(raw=result)

        # Navigate: result.root → SendMessageSuccessResponse
        root = getattr(result, "root", result)
        task = _safe_get(root, "result")  # Task object
        if task is None:
            return resp

        # State
        state_obj = _safe_get(task, "status", "state")
        if state_obj is not None:
            resp.state = (
                state_obj.value if hasattr(state_obj, "value") else str(state_obj)
            )

        # Status message (used for clarifications)
        resp.status_message = cls._extract_status_message(task)

        # Artifacts → text and data
        artifacts = getattr(task, "artifacts", None) or []
        resp.artifacts_raw = list(artifacts)

        for artifact in artifacts:
            for part in getattr(artifact, "parts", []):
                cls._extract_part(part, resp)

        return resp

    @classmethod
    def from_results(cls, results: list) -> List["A2AResponse"]:
        """Parse a list of raw A2A results into A2AResponse objects."""
        return [cls.parse(r) for r in results]

    # ── Batch helpers ───────────────────────────────────────────

    @classmethod
    def find_plan(cls, results: list) -> Optional[Dict[str, Any]]:
        """Extract the first plan (dict with ``tasks`` key) from results."""
        for resp in cls.from_results(results):
            if resp.data and "tasks" in resp.data:
                return resp.data
            # Fallback: try parsing text as JSON
            if resp.text:
                try:
                    parsed = json.loads(resp.text)
                    if isinstance(parsed, dict) and "tasks" in parsed:
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    @classmethod
    def find_clarification(cls, results: list) -> tuple:
        """Check if any result requests clarification.

        Returns:
            ``(True, message)`` if clarification needed, else ``(False, None)``.
        """
        for resp in cls.from_results(results):
            if resp.is_input_required:
                msg = resp.status_message or "Agent requires clarification"
                return True, msg
        return False, None

    @classmethod
    def collect_text(cls, results: list) -> List[str]:
        """Collect all text responses from results."""
        return [r.text for r in cls.from_results(results) if r.text]

    # ── Internal helpers ────────────────────────────────────────

    @staticmethod
    def _extract_status_message(task) -> Optional[str]:
        """Extract text from task.status.message.parts."""
        message = _safe_get(task, "status", "message")
        if message is None:
            return None
        for part in getattr(message, "parts", []):
            # part.root.text (wrapped) or part.text (direct)
            text = _safe_get(part, "root", "text")
            if text:
                return text
            text = getattr(part, "text", None)
            if text:
                return text
        return None

    @staticmethod
    def _extract_part(part, resp: "A2AResponse"):
        """Extract text/data from an artifact part into resp."""
        # Wrapped part: part.root.data or part.root.text
        root = getattr(part, "root", None)
        if root is not None:
            data = getattr(root, "data", None)
            if isinstance(data, dict) and resp.data is None:
                resp.data = data
                return
            text = getattr(root, "text", None)
            if text and resp.text is None:
                resp.text = text
                return

        # Direct part: part.data or part.text
        data = getattr(part, "data", None)
        if isinstance(data, dict) and resp.data is None:
            resp.data = data
            return
        text = getattr(part, "text", None)
        if text and resp.text is None:
            resp.text = text

    def __repr__(self) -> str:
        parts = [f"state={self.state!r}"]
        if self.text:
            parts.append(f"text={self.text[:60]!r}...")
        if self.data:
            parts.append(f"data_keys={list(self.data.keys())}")
        if self.is_input_required:
            parts.append("INPUT_REQUIRED")
        return f"A2AResponse({', '.join(parts)})"
