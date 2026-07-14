"""
abi_core.capabilities.viz — Visualize capability profiles.

Two renderers:

- ``render_bars(...)`` — a dependency-free text/terminal view (horizontal bars per
  dimension). Always available. Can overlay two profiles (e.g. task-required vs
  model-provided) to show the gap.
- ``render_radar_png(...)`` — a radar/spider chart saved as PNG. Requires
  ``matplotlib`` (optional). Raises a clear error if it isn't installed.

Both accept plain ``CapabilityProfile`` objects, so they work with seed,
measured, or task profiles alike.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from abi_core.capabilities.dimensions import CAPABILITY_DIMENSIONS, CapabilityProfile

# Shorter labels for compact terminal / radar rendering.
_SHORT_LABELS = {
    "code_generation": "code_gen",
    "tool_usage": "tool_use",
    "reasoning": "reason",
    "planning": "plan",
    "structured_output": "struct_out",
    "context_span": "ctx_span",
    "instruction_following": "instr_follow",
}


def render_bars(
    primary: CapabilityProfile,
    *,
    primary_label: str = "profile",
    secondary: Optional[CapabilityProfile] = None,
    secondary_label: str = "required",
    width: int = 24,
) -> str:
    """Render one or two profiles as text bars, one row per dimension.

    When ``secondary`` is given (e.g. the task requirement), each row shows both
    bars so the deficit is visible at a glance.

    Args:
        primary: The main profile (e.g. a model's capabilities).
        primary_label: Legend label for the primary profile.
        secondary: Optional second profile to overlay (e.g. task requirement).
        secondary_label: Legend label for the secondary profile.
        width: Bar width in characters (full = score 1.0).

    Returns:
        A multi-line string ready to print.
    """
    label_w = max(len(_SHORT_LABELS[d]) for d in CAPABILITY_DIMENSIONS)
    lines: List[str] = []

    if secondary is not None:
        lines.append(f"legend: █ {primary_label}   ░ {secondary_label}")

    for dim in CAPABILITY_DIMENSIONS:
        name = _SHORT_LABELS[dim].rjust(label_w)
        pv = primary.get(dim)
        pbar = "█" * round(pv * width)
        pbar = pbar.ljust(width)
        if secondary is None:
            lines.append(f"{name} |{pbar}| {pv:.2f}")
        else:
            sv = secondary.get(dim)
            sbar = ("░" * round(sv * width)).ljust(width)
            gap = max(0.0, sv - pv)
            marker = f"  gap {gap:.2f}" if gap > 0 else ""
            lines.append(f"{name} |{pbar}| {pv:.2f}  req {sv:.2f}{marker}")

    return "\n".join(lines)


def render_radar_png(
    primary: CapabilityProfile,
    path: str,
    *,
    primary_label: str = "profile",
    secondary: Optional[CapabilityProfile] = None,
    secondary_label: str = "required",
    title: str = "Capability Profile",
) -> str:
    """Render a radar (spider) chart to a PNG file.

    Requires ``matplotlib`` (optional dependency). Overlays ``secondary`` when
    provided so a task requirement and a model's capabilities can be compared.

    Args:
        primary: The main profile.
        path: Output PNG path.
        primary_label: Legend label for the primary profile.
        secondary: Optional second profile to overlay.
        secondary_label: Legend label for the secondary profile.
        title: Chart title.

    Returns:
        The path the PNG was written to.

    Raises:
        RuntimeError: if matplotlib is not installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless / no display
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise RuntimeError(
            "render_radar_png requires matplotlib. Install it with "
            "'pip install matplotlib' (optional dependency for capability visualization)."
        ) from e

    dims = list(CAPABILITY_DIMENSIONS)
    labels = [_SHORT_LABELS[d] for d in dims]
    n = len(dims)

    # Angles for each axis; close the polygon by repeating the first point.
    angles = [i / n * 2 * math.pi for i in range(n)]
    angles += angles[:1]

    def _values(profile: CapabilityProfile) -> List[float]:
        vals = [profile.get(d) for d in dims]
        return vals + vals[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"polar": True})
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids([a * 180 / math.pi for a in angles[:-1]], labels)
    ax.set_ylim(0, 1)
    ax.set_rgrids([0.2, 0.4, 0.6, 0.8, 1.0])

    p_vals = _values(primary)
    ax.plot(angles, p_vals, linewidth=2, label=primary_label)
    ax.fill(angles, p_vals, alpha=0.25)

    if secondary is not None:
        s_vals = _values(secondary)
        ax.plot(angles, s_vals, linewidth=2, label=secondary_label)
        ax.fill(angles, s_vals, alpha=0.15)

    ax.set_title(title, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    fig.savefig(path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    return path
