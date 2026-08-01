#!/usr/bin/env python3
"""Render the animated README demo of the Linux tray monitor.

The frames are produced by the application's own drawing code — ``render_icon``
for the gauge and ``format_panel_label``/``format_countdown`` for the text — so
the animation always matches what the tray actually shows. It is a rendering of
the monitor, not a screen capture of a desktop.

Usage:
    python3 linux/tools/render_demo.py [output.gif]
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "linux"))

import cairo  # noqa: E402
from PIL import Image  # noqa: E402

from claude_usage_monitor.formatting import format_countdown, format_panel_label  # noqa: E402
from claude_usage_monitor.icon import render_icon, severity_color  # noqa: E402

WIDTH, HEIGHT = 520, 150
ICON_RENDER_SIZE = 64
ICON_DRAW_SIZE = 104
FRAME_COUNT = 36
FRAME_DELAY_MS = 110
PALETTE_COLORS = 48

BACKGROUND = (0.11, 0.12, 0.14)
PANEL = (0.16, 0.17, 0.20)
TEXT = (0.90, 0.91, 0.93)
MUTED = (0.62, 0.64, 0.68)

# Start and end of the animated ramp for each window, in percent.
CLAUDE_SESSION_RANGE = (8.0, 94.0)
CLAUDE_WEEKLY_RANGE = (31.0, 68.0)
CODEX_SESSION_RANGE = (5.0, 47.0)

# Reset countdowns tick down over the animation, in seconds.
CLAUDE_SESSION_RESET = (4 * 3600, 40 * 60)
CLAUDE_WEEKLY_RESET = (5 * 86400, 3 * 86400)
CODEX_SESSION_RESET = (3 * 3600, 25 * 60)


def ease(progress: float) -> float:
    """Smooth in/out so the ramp does not look mechanical."""
    return 0.5 - 0.5 * math.cos(math.pi * progress)


def lerp(bounds: tuple[float, float], progress: float) -> float:
    start, end = bounds
    return start + (end - start) * progress


def _draw_text(ctx: cairo.Context, x: float, y: float, text: str, size: float, rgb, bold=False) -> None:
    ctx.select_font_face(
        "sans-serif",
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    ctx.set_source_rgb(*rgb)
    ctx.move_to(x, y)
    ctx.show_text(text)


def _draw_bar(ctx: cairo.Context, x: float, y: float, width: float, percentage: float) -> None:
    height = 6.0
    ctx.set_source_rgba(0.35, 0.37, 0.41, 1.0)
    ctx.rectangle(x, y, width, height)
    ctx.fill()

    filled = width * max(0.0, min(percentage, 100.0)) / 100.0
    if filled <= 0.0:
        return
    ctx.set_source_rgba(*severity_color(percentage))
    ctx.rectangle(x, y, filled, height)
    ctx.fill()


def _row(ctx: cairo.Context, y: float, label: str, percentage: float, reset_seconds: float) -> None:
    _draw_text(ctx, 168, y, label, 15, TEXT, bold=True)
    _draw_text(ctx, 232, y, f"{percentage:3.0f}%", 15, severity_color(percentage)[:3])
    _draw_bar(ctx, 282, y - 10, 150, percentage)
    _draw_text(ctx, 446, y, format_countdown(reset_seconds), 12, MUTED)


def render_frame(icon_path: Path, progress: float) -> Image.Image:
    claude_session = lerp(CLAUDE_SESSION_RANGE, progress)
    claude_weekly = lerp(CLAUDE_WEEKLY_RANGE, progress)
    codex_session = lerp(CODEX_SESSION_RANGE, progress)

    render_icon(icon_path, claude_session, claude_weekly, codex_session)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*BACKGROUND)
    ctx.paint()

    ctx.set_source_rgb(*PANEL)
    ctx.rectangle(0, 0, WIDTH, 34)
    ctx.fill()

    panel_label = format_panel_label(claude_session, claude_weekly, codex_session)
    _draw_text(ctx, 20, 22, "GNOME panel", 12, MUTED)
    _draw_text(ctx, 372, 22, panel_label, 13, TEXT, bold=True)

    icon = cairo.ImageSurface.create_from_png(str(icon_path))
    scale = ICON_DRAW_SIZE / ICON_RENDER_SIZE
    ctx.save()
    ctx.translate(36, 34 + (HEIGHT - 34 - ICON_DRAW_SIZE) / 2)
    ctx.scale(scale, scale)
    ctx.set_source_surface(icon, 0, 0)
    ctx.paint()
    ctx.restore()

    _row(ctx, 72, "Claude", claude_session, lerp(CLAUDE_SESSION_RESET, progress))
    _draw_text(ctx, 168, 88, "5h", 11, MUTED)
    _row(ctx, 108, "Claude", claude_weekly, lerp(CLAUDE_WEEKLY_RESET, progress))
    _draw_text(ctx, 168, 124, "7d", 11, MUTED)
    _row(ctx, 144, "Codex", codex_session, lerp(CODEX_SESSION_RESET, progress))

    surface.flush()
    data = bytes(surface.get_data())
    # Cairo hands out premultiplied BGRA; the demo is fully opaque, so a channel
    # swap is enough to get a correct RGB image.
    image = Image.frombuffer("RGBA", (WIDTH, HEIGHT), data, "raw", "BGRA", 0, 1)
    return image.convert("RGB")


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / ".github" / "linux-tray.gif"
    target.parent.mkdir(parents=True, exist_ok=True)

    frames: list[Image.Image] = []
    with tempfile.TemporaryDirectory() as tmp:
        icon_path = Path(tmp) / "icon.png"
        for index in range(FRAME_COUNT):
            # Ramp up over the first half, back down over the second.
            raw = index / (FRAME_COUNT - 1)
            progress = ease(raw * 2.0 if raw <= 0.5 else (1.0 - raw) * 2.0)
            frames.append(render_frame(icon_path, progress))

    # One palette for every frame: a per-frame palette would make the flat
    # background shimmer between frames.
    palette_source = frames[len(frames) // 2].quantize(
        colors=PALETTE_COLORS, method=Image.MEDIANCUT
    )
    frames = [frame.quantize(palette=palette_source, dither=Image.NONE) for frame in frames]

    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DELAY_MS,
        loop=0,
        optimize=True,
    )
    print(f"wrote {target} ({target.stat().st_size // 1024} KiB, {len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
