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


def format_percentage(percentage: float | None) -> str:
    return "—" if percentage is None else f"{percentage:.0f}%"


def format_panel_label(
    prefix: str,
    session_percentage: float | None,
    weekly_percentage: float | None,
) -> str:
    """Compact panel text for one source, e.g. ``Cl 80% · 40%``."""
    return (
        f"{prefix} {format_percentage(session_percentage)} · "
        f"{format_percentage(weekly_percentage)}"
    )
