"""Zombie Agent — code agent lifecycle state (one process, one task).

The code agent no longer exits when it answers the Orchestrator: it sends
its work to the run's reviewer, answers the reviewer's questions from what
it did, and ends when the reviewer says it is done — or when nobody
contacted it for EXECUTION_TIMEOUT.

Memory of what it did, why, when and how:
- the conversation of its generation, kept in a process-level checkpointer
  (``generation_memory()``, thread ``GENERATION_THREAD``);
- ``work_record``: the task, what it read, what it wrote, its TDD, timings.

Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.2-code-agent-lifecycle.md
"""

import asyncio
import time
from typing import Any, Dict, Optional

from abi_core.common.utils import abi_logging

GENERATION_THREAD = "generation"
MAX_QUESTIONS = 5   # per code agent, in total (user decision, 2026-10-08)

work_record: Dict[str, Any] = {}
questions_answered = 0
terminate_requested = False

_generation_memory = None
_last_contact: Optional[float] = None
_watchdog: Optional[asyncio.Task] = None


def generation_memory():
    """Checkpointer that outlives the generation call."""
    global _generation_memory
    if _generation_memory is None:
        from langgraph.checkpoint.memory import MemorySaver
        _generation_memory = MemorySaver()
    return _generation_memory


def generation_transcript(max_chars: int = 30000) -> str:
    """The generation conversation as text: the model's turns, the tools it
    called (name and arguments) and what they returned, oldest first.
    Truncated from the start if too long — the end is where the file was
    written."""
    try:
        snapshot = generation_memory().get_tuple({"configurable": {"thread_id": GENERATION_THREAD}})
    except Exception:
        snapshot = None
    if not snapshot:
        return ""
    messages = (snapshot.checkpoint.get("channel_values") or {}).get("messages") or []
    lines = []
    for m in messages:
        kind = type(m).__name__.replace("Message", "").replace("Chunk", "").lower()
        content = m.content if isinstance(m.content, str) else str(m.content)
        if content.strip():
            lines.append(f"[{kind}] {content.strip()[:2000]}")
        for call in getattr(m, "tool_calls", None) or []:
            lines.append(f"[tool call] {call.get('name')}({str(call.get('args'))[:500]})")
    text = "\n".join(lines)
    return text if len(text) <= max_chars else "…\n" + text[-max_chars:]


def touch() -> None:
    """The reviewer contacted us (or we just reached it): restart the clock."""
    global _last_contact
    _last_contact = time.time()


def request_termination(reason: str) -> None:
    """End after the current response is sent (main.py's on_response_sent)."""
    global terminate_requested
    terminate_requested = True
    abi_logging(f"[🧟] Code agent will terminate after this response: {reason}")


async def terminate_now(agent_name: str, reason: str) -> None:
    from abi_core.common.context_loader import self_deregister
    abi_logging(f"[🧟] Code agent terminating: {reason}")
    await self_deregister(agent_name=agent_name, destroy=True)


def start_watchdog(agent_name: str, idle_timeout: float) -> None:
    """Terminate if the reviewer goes silent for ``idle_timeout`` seconds."""
    global _watchdog
    touch()
    if _watchdog is not None and not _watchdog.done():
        return

    async def _watch():
        while True:
            await asyncio.sleep(min(10.0, idle_timeout))
            if terminate_requested:
                return
            if time.time() - (_last_contact or 0) > idle_timeout:
                await terminate_now(agent_name, f"no contact from the reviewer in {int(idle_timeout)}s")
                return

    _watchdog = asyncio.create_task(_watch())
