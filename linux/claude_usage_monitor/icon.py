"""Tray icon rendering: concentric gauges, one ring per usage window.

Every indicator draws the same two rings — the outer one for the 5-hour window,
the inner one for the 7-day window — plus a single letter in the free core so
the Claude and the Codex icon stay apart at panel size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cairo

from .config import CRITICAL_THRESHOLD, WARN_THRESHOLD

SIZE = 64
TRACK_RGBA = (0.60, 0.62, 0.66, 0.45)
GLYPH_RGBA = (0.74, 0.76, 0.80, 0.95)
FAULT_RGBA = (0.96, 0.26, 0.21, 1.0)
GLYPH_SIZE = 22.0
FAULT_RADIUS = 7.0


@dataclass(frozen=True)
class RingSpec:
    radius: float
    width: float


OUTER = RingSpec(radius=26.0, width=6.0)  # 5-hour window
INNER = RingSpec(radius=18.0, width=6.0)  # 7-day window

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


def _draw_gauge(ctx: cairo.Context, ring: RingSpec, percentage: float | None) -> None:
    """Draw the track and, unless *percentage* is None, the filled arc."""
    center = SIZE / 2.0
    ctx.set_line_width(ring.width)
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)

    ctx.set_source_rgba(*TRACK_RGBA)
    ctx.arc(center, center, ring.radius, 0.0, 2.0 * math.pi)
    ctx.stroke()

    if percentage is None:
        return

    fraction = max(0.0, min(percentage, 100.0)) / 100.0
    if fraction <= 0.0:
        return

    ctx.set_source_rgba(*severity_color(percentage))
    start = -math.pi / 2.0
    sweep = max(fraction * 2.0 * math.pi, MIN_SWEEP)
    ctx.arc(center, center, ring.radius, start, start + sweep)
    ctx.stroke()


def _draw_glyph(ctx: cairo.Context, glyph: str) -> None:
    """Centre the source letter in the free core inside the inner ring."""
    if not glyph:
        return
    center = SIZE / 2.0
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(GLYPH_SIZE)
    extents = ctx.text_extents(glyph)
    ctx.set_source_rgba(*GLYPH_RGBA)
    ctx.move_to(
        center - extents.width / 2.0 - extents.x_bearing,
        center - extents.height / 2.0 - extents.y_bearing,
    )
    ctx.show_text(glyph)


def _draw_fault_dot(ctx: cairo.Context) -> None:
    """Red marker in the top-right corner, used by the error icon."""
    ctx.set_source_rgba(*FAULT_RGBA)
    ctx.arc(SIZE - FAULT_RADIUS - 2.0, FAULT_RADIUS + 2.0, FAULT_RADIUS, 0.0, 2.0 * math.pi)
    ctx.fill()


def _write(surface: cairo.ImageSurface, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    surface.write_to_png(str(path))
    return path


def render_rings(
    path: Path,
    pairs: Sequence[tuple[RingSpec, float | None]],
    glyph: str = "",
) -> Path:
    """Write a PNG gauge to *path*.

    Each pair is a ring and its percentage; None draws the bare track, which is
    how a window the source does not report is shown.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    ctx = cairo.Context(surface)
    for ring, percentage in pairs:
        _draw_gauge(ctx, ring, percentage)
    _draw_glyph(ctx, glyph)
    return _write(surface, path)


def render_error(path: Path, glyph: str = "") -> Path:
    """Write the fault icon: empty tracks, the source letter, a red marker."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    ctx = cairo.Context(surface)
    for ring in (OUTER, INNER):
        _draw_gauge(ctx, ring, None)
    _draw_glyph(ctx, glyph)
    _draw_fault_dot(ctx)
    return _write(surface, path)
