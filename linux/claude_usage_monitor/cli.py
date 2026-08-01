"""Terminal output modes — used for --once, --watch and as a headless fallback."""

from __future__ import annotations

import json
import sys
import time

from .formatting import format_bar, format_countdown
from .poller import Snapshot, poll_once

RESET_SEQUENCE = "\033[2J\033[H"


def _usage_line(label: str, window) -> str:
    return (
        f"  {label:<5} {format_bar(window.percentage)} {window.percentage:5.1f}%"
        f"   Reset in {format_countdown(window.seconds_until_reset)}"
    )


def _render_text(snapshot: Snapshot) -> str:
    lines: list[str] = ["Claude Code", ""]

    if snapshot.usage is None:
        hint = " — bitte 'claude' neu einloggen" if snapshot.needs_login else ""
        lines.append(f"  Fehler: {snapshot.error}{hint}")
    else:
        lines.append(_usage_line("5h", snapshot.usage.session))
        lines.append(_usage_line("7d", snapshot.usage.weekly))

    if snapshot.codex is not None or snapshot.codex_error is not None:
        lines += ["", "Codex", ""]
        if snapshot.codex_error is not None:
            lines.append(f"  Fehler: {snapshot.codex_error}")
        else:
            if snapshot.codex.short is not None:
                lines.append(_usage_line("5h", snapshot.codex.short))
            if snapshot.codex.long is not None:
                lines.append(_usage_line("7d", snapshot.codex.long))

    lines += ["", f"  Stand: {snapshot.at.astimezone().strftime('%H:%M:%S')}"]
    return "\n".join(lines)


def _window_json(window) -> dict | None:
    if window is None:
        return None
    return {
        "utilization": window.percentage,
        "resets_at": window.resets_at.isoformat() if window.resets_at else None,
        "seconds_until_reset": window.seconds_until_reset,
    }


def _render_json(snapshot: Snapshot) -> str:
    if snapshot.usage is None:
        claude = {"ok": False, "error": snapshot.error, "needs_login": snapshot.needs_login}
    else:
        claude = {
            "ok": True,
            "five_hour": _window_json(snapshot.usage.session),
            "seven_day": _window_json(snapshot.usage.weekly),
        }

    payload = {"claude": claude, "fetched_at": snapshot.at.isoformat()}

    if snapshot.codex_error is not None:
        payload["codex"] = {"ok": False, "error": snapshot.codex_error}
    elif snapshot.codex is not None:
        payload["codex"] = {
            "ok": True,
            "five_hour": _window_json(snapshot.codex.short),
            "seven_day": _window_json(snapshot.codex.long),
        }

    return json.dumps(payload, indent=2)


def run_once(as_json: bool = False) -> int:
    snapshot = poll_once()
    print(_render_json(snapshot) if as_json else _render_text(snapshot))
    return 0 if snapshot.usage is not None else 1


def run_watch(interval_seconds: int) -> int:
    try:
        while True:
            snapshot = poll_once()
            sys.stdout.write(RESET_SEQUENCE + _render_text(snapshot) + "\n")
            sys.stdout.flush()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        return 0
