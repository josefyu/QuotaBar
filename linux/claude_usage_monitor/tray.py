"""Tray coordinator: owns the config, the poller and one indicator per source.

Claude is always shown; the Codex indicator only appears once a poll reports
that the Codex CLI is signed in.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .config import Config  # noqa: E402
from .indicator import (  # noqa: E402
    IndicatorActions,
    IndicatorSpec,
    MenuState,
    Notification,
    UsageIndicator,
)
from .poller import Poller, Snapshot, codex_is_visible  # noqa: E402

APP_ID = "claude-usage-monitor"
MENU_TICK_SECONDS = 30

CLAUDE_SPEC = IndicatorSpec(
    app_id=APP_ID,
    source="Claude",
    glyph="C",
    label_prefix="Cl",
    icon_basename="claude",
)
CODEX_SPEC = IndicatorSpec(
    app_id=f"{APP_ID}-codex",
    source="Codex",
    glyph="X",
    label_prefix="Cx",
    icon_basename="codex",
)


def load_indicator_module():
    """Import the AppIndicator binding, preferring the Ayatana variant."""
    for namespace, version in (("AyatanaAppIndicator3", "0.1"), ("AppIndicator3", "0.1")):
        try:
            gi.require_version(namespace, version)
            return importlib.import_module(f"gi.repository.{namespace}")
        except (ValueError, ImportError):
            continue
    return None


def _icon_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / APP_ID


class TrayApp:
    def __init__(self, appindicator, config: Config) -> None:
        self._config = config
        self._icon_dir = _icon_dir()
        self._icon_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot: Snapshot | None = None
        self._notify = self._init_notifications()

        actions = IndicatorActions(
            refresh=lambda: self._poller.refresh_now(),
            set_interval=self._on_interval,
            set_show_label=self._on_show_label,
            set_notify=self._on_notify,
            quit=self._on_quit,
        )
        self._claude = UsageIndicator(
            appindicator, CLAUDE_SPEC, actions, self._menu_state(), self._icon_dir
        )
        self._codex = UsageIndicator(
            appindicator, CODEX_SPEC, actions, self._menu_state(), self._icon_dir
        )
        self._codex.set_active(False)

        self._poller = Poller(self._on_snapshot_threadsafe, config.poll_interval_seconds)

    def _menu_state(self) -> MenuState:
        return MenuState(
            poll_interval_seconds=self._config.poll_interval_seconds,
            show_panel_label=self._config.show_panel_label,
            notify_on_thresholds=self._config.notify_on_thresholds,
            notify_available=self._notify is not None,
        )

    # ------------------------------------------------------------ settings

    def _sync_menus(self) -> None:
        state = self._menu_state()
        for indicator in (self._claude, self._codex):
            indicator.sync_state(state)

    def _on_interval(self, seconds: int) -> None:
        if seconds == self._config.poll_interval_seconds:
            return
        self._config.poll_interval_seconds = seconds
        self._config.save()
        self._poller.set_interval(seconds)
        self._sync_menus()

    def _on_show_label(self, enabled: bool) -> None:
        if enabled == self._config.show_panel_label:
            return
        self._config.show_panel_label = enabled
        self._config.save()
        self._sync_menus()
        if self._snapshot is not None:
            self._apply_snapshot(self._snapshot)

    def _on_notify(self, enabled: bool) -> None:
        if enabled == self._config.notify_on_thresholds:
            return
        self._config.notify_on_thresholds = enabled
        self._config.save()
        self._sync_menus()

    def _on_quit(self) -> None:
        self._poller.stop()
        Gtk.main_quit()

    # ------------------------------------------------------------- updates

    def _on_snapshot_threadsafe(self, snapshot: Snapshot) -> None:
        GLib.idle_add(self._apply_snapshot, snapshot)

    def _apply_snapshot(self, snapshot: Snapshot) -> bool:
        self._snapshot = snapshot
        pending: list[Notification] = []

        if snapshot.usage is None:
            hint = " — bitte 'claude' neu einloggen" if snapshot.needs_login else ""
            self._claude.show_error(f"Fehler: {snapshot.error}{hint}")
        else:
            pending += self._claude.update(
                snapshot.usage.session, snapshot.usage.weekly, snapshot.usage.fetched_at
            )

        self._codex.set_active(codex_is_visible(snapshot))
        if snapshot.codex_error is not None:
            self._codex.show_error(f"Fehler: {snapshot.codex_error}")
        elif snapshot.codex is not None:
            pending += self._codex.update(
                snapshot.codex.short, snapshot.codex.long, snapshot.codex.fetched_at
            )

        self._show_notifications(pending)
        return False

    def _tick(self) -> bool:
        """Keep the reset countdowns moving between polls."""
        if self._snapshot is not None:
            self._apply_snapshot(self._snapshot)
        return True

    # ------------------------------------------------------- notifications

    def _init_notifications(self):
        try:
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify

            Notify.init("Claude Usage Monitor")
            return Notify
        except (ValueError, ImportError):
            return None

    def _show_notifications(self, pending: list[Notification]) -> None:
        if self._notify is None or not self._config.notify_on_thresholds:
            return
        for item in pending:
            try:
                self._notify.Notification.new(item.title, item.body, "dialog-warning").show()
            except GLib.Error:
                pass

    # ----------------------------------------------------------------- run

    def run(self) -> int:
        self._poller.start()
        GLib.timeout_add_seconds(MENU_TICK_SECONDS, self._tick)
        Gtk.main()
        return 0
