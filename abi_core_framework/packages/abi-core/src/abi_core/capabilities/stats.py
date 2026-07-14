"""
abi_core.capabilities.stats — Confidence intervals for probe success ratios.

A probe is run N times against a (non-deterministic) model; its score is the
success ratio. To know when that ratio is reliable, we use the **Wilson score
interval** (better than the normal approximation for p near 0/1 and small N),
and an adaptive stopping rule: keep sampling until the 95% interval is narrow
enough, within a floor/ceiling on N.

See .abi/specs/capability-profiling-methodology.md § P1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# z for a 95% two-sided confidence interval.
Z_95 = 1.959963984540054

# Adaptive sampling defaults (dev-time profiling; offline).
DEFAULT_N_MIN = 10
DEFAULT_N_MAX = 40
DEFAULT_CI_WIDTH = 0.15


@dataclass(frozen=True)
class WilsonInterval:
    """A Wilson score interval for a proportion."""

    ratio: float      # observed success ratio (successes / n)
    low: float        # lower bound, clamped to [0, 1]
    high: float       # upper bound, clamped to [0, 1]
    n: int
    successes: int

    @property
    def width(self) -> float:
        return self.high - self.low


def wilson_interval(successes: int, n: int, z: float = Z_95) -> WilsonInterval:
    """Wilson score interval for ``successes`` out of ``n`` trials.

    Args:
        successes: Number of successful trials (0 <= successes <= n).
        n: Total trials. If 0, returns the maximally-uncertain [0, 1].
        z: z-score for the desired confidence (default 95%).

    Returns:
        A :class:`WilsonInterval` with bounds clamped to ``[0, 1]``.
    """
    if n <= 0:
        return WilsonInterval(ratio=0.0, low=0.0, high=1.0, n=0, successes=0)
    if successes < 0 or successes > n:
        raise ValueError(f"successes ({successes}) must be in [0, n={n}]")

    p_hat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))

    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return WilsonInterval(ratio=p_hat, low=low, high=high, n=n, successes=successes)


def should_stop(
    successes: int,
    n: int,
    *,
    n_min: int = DEFAULT_N_MIN,
    n_max: int = DEFAULT_N_MAX,
    ci_width: float = DEFAULT_CI_WIDTH,
    z: float = Z_95,
) -> bool:
    """Adaptive stopping rule for probe repetitions.

    Stop when we've hit the ceiling, or when we've run at least the floor and the
    95% Wilson interval is narrow enough.

    Args:
        successes: Successful trials so far.
        n: Trials so far.
        n_min: Minimum trials before we may stop early.
        n_max: Hard ceiling on trials.
        ci_width: Stop early once the interval width is <= this.
        z: z-score for the interval.

    Returns:
        ``True`` if sampling should stop.
    """
    if n >= n_max:
        return True
    if n < n_min:
        return False
    return wilson_interval(successes, n, z=z).width <= ci_width
