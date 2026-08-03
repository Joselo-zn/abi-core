"""
abi_core.common.retry — Shared retry-with-backoff primitive.

New primitive for `@agent.task_async`/`@agent.task_schedule` (see
.abi/tsd/2026-08-02-retry-primitive-scope.md for why the two existing retry
loops in `tool_graph.py`/`semantic_tools.py` are NOT migrated onto this).

Uses true exponential backoff (`base_delay * 2**attempt`) — unlike
`tool_graph.py`'s loop, which is linear despite being commented "exponential".
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Optional


async def retry_with_backoff(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: Optional[float] = None,
    retryable: Optional[Callable[[BaseException], bool]] = None,
    on_retry: Optional[Callable[[int, BaseException], Any]] = None,
    **kwargs: Any,
) -> Any:
    """Call ``fn(*args, **kwargs)``, retrying on failure with exponential backoff.

    Delay before attempt N (1-indexed) is ``base_delay * 2**(N-1)``, capped at
    ``max_delay`` if given. ``fn`` may be sync or async.

    ``on_retry(attempt, exc)`` — 1-indexed attempt number, runs BEFORE the
    sleep after each failed attempt (awaited if it returns an awaitable).
    This is the audit hook `task_async`/`task_schedule` use to log every
    failed attempt structurally before backing off.

    ``retryable(exc) -> bool`` — lets a caller opt an exception OUT of retry
    (re-raises immediately if it returns False). Default: any ``Exception``
    is retryable. ``BaseException`` subclasses that aren't ``Exception``
    (e.g. ``asyncio.CancelledError``, ``KeyboardInterrupt``) are never
    caught here — they propagate immediately, same as normal Python control
    flow expects.

    Raises the last exception once ``max_retries`` attempts are exhausted.
    """
    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:  # noqa: BLE001 — intentionally broad, filtered by `retryable`
            if retryable is not None and not retryable(exc):
                raise
            last_exc = exc
            if on_retry is not None:
                hook_result = on_retry(attempt, exc)
                if inspect.isawaitable(hook_result):
                    await hook_result
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                if max_delay is not None:
                    delay = min(delay, max_delay)
                await asyncio.sleep(delay)

    assert last_exc is not None  # max_retries >= 1 guarantees at least one attempt
    raise last_exc
