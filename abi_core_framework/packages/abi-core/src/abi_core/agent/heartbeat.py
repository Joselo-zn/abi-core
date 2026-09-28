# abi_core/agent/heartbeat.py
"""
Generic task-heartbeat artifact — emitter + inactivity watchdog.

See .abi/specs/not-implemented/generic-task-heartbeat-artifact.md.

Two halves, transport-agnostic — neither one hardcodes a wait time; every
interval/grace period is a parameter the caller picks for its own task, not
a constant borrowed from an unrelated call site:

- `emit_heartbeats_while()`: runs a coroutine in the background, calling a
  caller-supplied `emit_fn()` on every `interval` it hasn't finished yet.
  The caller decides HOW a heartbeat is sent — an A2A status event today, a
  different transport for a future DAG/pipeline stage tomorrow.

- `InactivityWatchdog`: tracked by whoever is WAITING for a task. Reset on
  every event received (heartbeat or real data) via `touch()`; only
  declares a key dead once `grace_period` elapses with NOTHING at all —
  not a fixed wall-clock budget for the whole task, and not one shared
  number for every key.

Core loop of `emit_heartbeats_while` mirrors `AbiAgent._run_with_heartbeat`'s
already-proven cancellation-safe pattern (`asyncio.wait_for(asyncio.shield(task),
...)` — a timed-out wait never abandons the underlying coroutine mid-flight)
but decoupled from `AgentResponse`/`self`, so it works for a caller that
isn't an `AbiAgent` method — a raw A2A client loop, or a future pipeline
stage.
"""

import asyncio
import inspect
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Union


class HeartbeatTimeoutError(TimeoutError):
    """Raised by `emit_heartbeats_while` only when `max_wait` is given and
    elapses — same semantics as `AbiAgent._run_with_heartbeat`'s version."""


async def emit_heartbeats_while(
    coro: Awaitable[Any],
    emit_fn: Optional[Callable[[], Union[None, Awaitable[None]]]],
    interval: float,
    max_wait: Optional[float] = None,
) -> Any:
    """Run `coro` in the background; every `interval` seconds it hasn't
    finished, call `emit_fn()` to signal liveness. Returns `coro`'s result
    once it completes.

    `emit_fn` may be sync or async, and may be `None` (just waits, no
    signal — useful for a caller that only wants the cancellation-safe
    wait loop). `interval` has no default on purpose: pick the tempo that
    fits the task at hand, don't inherit one from a different call site.
    """
    elapsed = 0.0
    task = asyncio.create_task(coro)

    while not task.done():
        if max_wait is not None:
            remaining = max_wait - elapsed
            if remaining <= 0:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                raise HeartbeatTimeoutError(
                    f"Task exceeded max_wait ({int(max_wait)}s) with no result."
                )
            wait_chunk = min(interval, remaining)
        else:
            wait_chunk = interval

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=wait_chunk)
        except asyncio.TimeoutError:
            elapsed += wait_chunk
            if not task.done() and emit_fn is not None:
                result = emit_fn()
                if inspect.isawaitable(result):
                    await result

    return task.result()


class InactivityWatchdog:
    """Tracks liveness of keyed tasks by inactivity, not a fixed wall-clock
    budget. Each key can get its own grace period — pass a dict of per-key
    overrides (with an optional "default" entry), or a single float applied
    to every key.

    Usage:
        watchdog = InactivityWatchdog(grace_period=180.0)
        watchdog.touch(task_id)       # call on every event seen (heartbeat or real data)
        watchdog.is_expired(task_id)  # True once grace_period passed with no touch()
    """

    def __init__(self, grace_period: Union[float, Dict[str, float]] = 180.0):
        self._grace_period = grace_period
        self._last_seen: Dict[str, float] = {}

    def _grace_for(self, key: str) -> float:
        if isinstance(self._grace_period, dict):
            return self._grace_period.get(key, self._grace_period.get("default", 180.0))
        return self._grace_period

    def touch(self, key: str) -> None:
        """Record that an event (heartbeat or real data) was just seen for `key`."""
        self._last_seen[key] = time.monotonic()

    def is_expired(self, key: str) -> bool:
        """True once the grace period has elapsed since the last `touch()`
        for `key`. `False` if `key` was never touched — that's the caller's
        job to do before relying on this."""
        last = self._last_seen.get(key)
        if last is None:
            return False
        return (time.monotonic() - last) > self._grace_for(key)

    def forget(self, key: str) -> None:
        """Stop tracking `key` — task finished or failed, no need to watch
        it anymore."""
        self._last_seen.pop(key, None)
