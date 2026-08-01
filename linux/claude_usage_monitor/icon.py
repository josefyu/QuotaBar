"""Tray icon rendering: concentric gauges, one ring per usage window.

Outer ring is the Claude 5-hour window, middle ring the Claude 7-day window.
The innermost ring is the Codex 5-hour window and is only drawn when the Codex
CLI is signed in, so a Claude-only setup keeps a two-ring icon.
"""

from __future__ import annotations

import math
from pathlib import Path

import cairo

from .config import CRITICAL_THRESHOLD, WARN_THRESHOLD

SIZE = 64
TRACK_RGBA = (0.60, 0.62, 0.66, 0.45)
ERROR_RGBA = (0.55, 0.57, 0.60, 0.90)

CLAUDE_SESSION = {"radius": 26.0, "width": 6.0}
CLAUDE_WEEKLY = {"radius": 18.0, "width": 6.0}
CODEX_SESSION = {"radius": 10.0, "width": 6.0}

# Smallest arc a non-zero gauge is allowed to draw, so a 1% reading stays
# visible instead of collapsing into the track.
MIN_SWEEP = math.radians(14.0)


def severity_color(percentage: float) -> tuple[float, float, float, float]:
    if percentage >= CRITICAL_THRESHOLD:
        return (0.96, 0.26, 0.21, 1.0)  # red
    if percentage >= WARN_THRESHOLD:
        return (1.00, 0.60, 0.00, 1.0)  # orange
    if percentage >= 50.0:
        return (0.96, 0.77, 0.26, 1.0)  # yellow
    return (0.30, 0.75, 0.36, 1.0)  # green


def _draw_gauge(ctx: cairo.Context, ring: dict, percentage: float) -> None:
    center = SIZE / 2.0
    radius = ring["radius"]
    ctx.set_line_width(ring["width"])
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)

    ctx.set_source_rgba(*TRACK_RGBA)
    ctx.arc(center, center, radius, 0.0, 2.0 * math.pi)
    ctx.stroke()

    fraction = max(0.0, min(percentage, 100.0)) / 100.0
    if fraction <= 0.0:
        return

    ctx.set_source_rgba(*severity_color(percentage))
    start = -math.pi / 2.0
    sweep = max(fraction * 2.0 * math.pi, MIN_SWEEP)
    ctx.arc(center, center, radius, start, start + sweep)
    ctx.stroke()


def _draw_error(ctx: cairo.Context) -> None:
    center = SIZE / 2.0
    ctx.set_line_width(7.0)
    ctx.set_source_rgba(*ERROR_RGBA)
    ctx.arc(center, center, CLAUDE_SESSION["radius"], 0.0, 2.0 * math.pi)
    ctx.stroke()
    ctx.set_line_width(8.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(center, center - 11.0)
    ctx.line_to(center, center + 3.0)
    ctx.stroke()
    ctx.move_to(center, center + 11.0)
    ctx.line_to(center, center + 11.5)
    ctx.stroke()


def render_icon(
    path: Path,
    session_percentage: float | None,
    weekly_percentage: float | None,
    codex_percentage: float | None = None,
) -> Path:
    """Write a PNG gauge to *path*.

    Pass None for both Claude values to draw the error icon. The Codex ring is
    skipped when *codex_percentage* is None.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    ctx = cairo.Context(surface)

    if session_percentage is None and weekly_percentage is None:
        _draw_error(ctx)
    else:
        _draw_gauge(ctx, CLAUDE_SESSION, session_percentage or 0.0)
        _draw_gauge(ctx, CLAUDE_WEEKLY, weekly_percentage or 0.0)
        if codex_percentage is not None:
            _draw_gauge(ctx, CODEX_SESSION, codex_percentage)

    path.parent.mkdir(parents=True, exist_ok=True)
    surface.write_to_png(str(path))
    return path
