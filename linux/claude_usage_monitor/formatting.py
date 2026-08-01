"""Shared human-readable formatting for tray menu and terminal output."""

from __future__ import annotations

from .api import UsageWindow


def format_countdown(seconds: float | None) -> str:
    if seconds is None:
        return "unbekannt"
    if seconds <= 0:
        return "jetzt"

    total_minutes = int(seconds // 60)
    days, remainder = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def format_window(label: str, window: UsageWindow) -> str:
    return (
        f"{label}: {window.percentage:.0f}%  "
        f"(Reset in {format_countdown(window.seconds_until_reset)})"
    )


def format_bar(percentage: float, width: int = 24) -> str:
    filled = int(round(max(0.0, min(percentage, 100.0)) / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def format_panel_label(
    session_percentage: float,
    weekly_percentage: float,
    codex_percentage: float | None = None,
) -> str:
    label = f"{session_percentage:.0f}% · {weekly_percentage:.0f}%"
    if codex_percentage is not None:
        label += f" | Cx {codex_percentage:.0f}%"
    return label
