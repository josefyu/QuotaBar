"""GNOME/AppIndicator tray widget showing the 5h and 7d Claude usage windows."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .api import UsageData  # noqa: E402
from .config import ALLOWED_INTERVALS, CRITICAL_THRESHOLD, WARN_THRESHOLD, Config  # noqa: E402
from .formatting import format_countdown, format_panel_label  # noqa: E402
from .icon import render_icon  # noqa: E402
from .poller import Poller, Snapshot  # noqa: E402

APP_ID = "claude-usage-monitor"
MENU_TICK_SECONDS = 30


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
        self._appindicator = appindicator
        self._config = config
        self._icon_dir = _icon_dir()
        self._icon_slot = 0
        self._snapshot: Snapshot | None = None
        self._notified_levels: dict[str, str] = {}
        self._notify = self._init_notifications()

        self._indicator = appindicator.Indicator.new(
            APP_ID,
            "dialog-information",
            appindicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self._indicator.set_icon_theme_path(str(self._icon_dir))

        self._build_menu()
        self._poller = Poller(self._on_snapshot_threadsafe, config.poll_interval_seconds)

    # ---------------------------------------------------------------- menu

    def _build_menu(self) -> None:
        self._menu = Gtk.Menu()

        self._session_item = Gtk.MenuItem(label="5h: —")
        self._session_item.set_sensitive(False)
        self._menu.append(self._session_item)

        self._weekly_item = Gtk.MenuItem(label="7d: —")
        self._weekly_item.set_sensitive(False)
        self._menu.append(self._weekly_item)

        # Codex rows stay hidden until a poll reports that Codex is configured.
        self._codex_separator = Gtk.SeparatorMenuItem()
        self._menu.append(self._codex_separator)
        self._codex_items: list[Gtk.MenuItem] = []
        for _ in range(2):
            item = Gtk.MenuItem(label="")
            item.set_sensitive(False)
            self._codex_items.append(item)
            self._menu.append(item)

        self._status_item = Gtk.MenuItem(label="Lade …")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        refresh_item = Gtk.MenuItem(label="Jetzt aktualisieren")
        refresh_item.connect("activate", lambda _item: self._poller.refresh_now())
        self._menu.append(refresh_item)

        self._menu.append(self._build_interval_item())

        label_item = Gtk.CheckMenuItem(label="Text im Panel")
        label_item.set_active(self._config.show_panel_label)
        label_item.connect("toggled", self._on_toggle_label)
        self._menu.append(label_item)

        notify_item = Gtk.CheckMenuItem(label="Benachrichtigungen")
        notify_item.set_active(self._config.notify_on_thresholds)
        notify_item.set_sensitive(self._notify is not None)
        notify_item.connect("toggled", self._on_toggle_notify)
        self._menu.append(notify_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Beenden")
        quit_item.connect("activate", self._on_quit)
        self._menu.append(quit_item)

        self._menu.show_all()
        self._set_codex_rows([])
        self._indicator.set_menu(self._menu)

    def _build_interval_item(self) -> Gtk.MenuItem:
        parent = Gtk.MenuItem(label="Aktualisierungsintervall")
        submenu = Gtk.Menu()
        group: list[Gtk.RadioMenuItem] = []

        for seconds in ALLOWED_INTERVALS:
            item = Gtk.RadioMenuItem(label=f"{seconds // 60} min")
            if group:
                item.join_group(group[0])
            group.append(item)
            item.set_active(seconds == self._config.poll_interval_seconds)
            item.connect("toggled", self._on_interval_selected, seconds)
            submenu.append(item)

        parent.set_submenu(submenu)
        return parent

    # ------------------------------------------------------------ handlers

    def _on_interval_selected(self, item: Gtk.RadioMenuItem, seconds: int) -> None:
        if not item.get_active() or seconds == self._config.poll_interval_seconds:
            return
        self._config.poll_interval_seconds = seconds
        self._config.save()
        self._poller.set_interval(seconds)

    def _on_toggle_label(self, item: Gtk.CheckMenuItem) -> None:
        self._config.show_panel_label = item.get_active()
        self._config.save()
        self._apply_panel_label()

    def _on_toggle_notify(self, item: Gtk.CheckMenuItem) -> None:
        self._config.notify_on_thresholds = item.get_active()
        self._config.save()

    def _on_quit(self, _item: Gtk.MenuItem) -> None:
        self._poller.stop()
        Gtk.main_quit()

    # ------------------------------------------------------------- updates

    def _on_snapshot_threadsafe(self, snapshot: Snapshot) -> None:
        GLib.idle_add(self._apply_snapshot, snapshot)

    def _apply_snapshot(self, snapshot: Snapshot) -> bool:
        self._snapshot = snapshot
        usage = snapshot.usage
        self._refresh_codex_rows(snapshot)

        if usage is None:
            self._session_item.set_label("5h: nicht verfuegbar")
            self._weekly_item.set_label("7d: nicht verfuegbar")
            hint = " — bitte 'claude' neu einloggen" if snapshot.needs_login else ""
            self._status_item.set_label(f"Fehler: {snapshot.error}{hint}")
            self._set_icon(None, None)
            self._indicator.set_label("", "")
            self._indicator.set_title("Claude Usage — Fehler")
            return False

        self._refresh_usage_labels(usage)
        self._set_icon(
            usage.session.percentage,
            usage.weekly.percentage,
            self._codex_session_percentage(),
        )
        self._apply_panel_label()
        self._maybe_notify(usage)
        return False

    def _refresh_usage_labels(self, usage: UsageData) -> None:
        self._session_item.set_label(
            f"5h: {usage.session.percentage:.0f}%  ·  Reset in "
            f"{format_countdown(usage.session.seconds_until_reset)}"
        )
        self._weekly_item.set_label(
            f"7d: {usage.weekly.percentage:.0f}%  ·  Reset in "
            f"{format_countdown(usage.weekly.seconds_until_reset)}"
        )
        self._status_item.set_label(
            f"Stand: {usage.fetched_at.astimezone().strftime('%H:%M:%S')}"
        )
        title = (
            f"Claude Usage — 5h {usage.session.percentage:.0f}%, "
            f"7d {usage.weekly.percentage:.0f}%"
        )
        codex = self._codex_session_percentage()
        if codex is not None:
            title += f" · Codex 5h {codex:.0f}%"
        self._indicator.set_title(title)

    def _set_codex_rows(self, labels: list[str]) -> None:
        """Show one menu row per label; hide the rest and the section divider."""
        self._codex_separator.set_visible(bool(labels))
        for index, item in enumerate(self._codex_items):
            if index < len(labels):
                item.set_label(labels[index])
                item.set_visible(True)
            else:
                item.set_visible(False)

    def _refresh_codex_rows(self, snapshot: Snapshot) -> None:
        if snapshot.codex_error is not None:
            self._set_codex_rows([f"Codex: {snapshot.codex_error}"])
            return
        if snapshot.codex is None:
            self._set_codex_rows([])
            return

        labels = []
        for prefix, window in (("5h", snapshot.codex.short), ("7d", snapshot.codex.long)):
            if window is None:
                continue
            labels.append(
                f"Codex {prefix}: {window.percentage:.0f}%  ·  Reset in "
                f"{format_countdown(window.seconds_until_reset)}"
            )
        self._set_codex_rows(labels)

    def _codex_session_percentage(self) -> float | None:
        """Codex 5h window, drawn as the innermost icon ring."""
        if self._snapshot is None or self._snapshot.codex is None:
            return None
        window = self._snapshot.codex.short or self._snapshot.codex.long
        return window.percentage if window is not None else None

    def _codex_headline_percentage(self) -> float | None:
        """Highest Codex window, used for the compact panel label."""
        if self._snapshot is None or self._snapshot.codex is None:
            return None
        values = [
            window.percentage
            for window in (self._snapshot.codex.short, self._snapshot.codex.long)
            if window is not None
        ]
        return max(values) if values else None

    def _tick(self) -> bool:
        """Keep the reset countdowns moving between polls."""
        if self._snapshot is None:
            return True
        if self._snapshot.usage is not None:
            self._refresh_usage_labels(self._snapshot.usage)
        self._refresh_codex_rows(self._snapshot)
        return True

    def _apply_panel_label(self) -> None:
        if self._snapshot is None or self._snapshot.usage is None:
            return
        if not self._config.show_panel_label:
            self._indicator.set_label("", "")
            return
        usage = self._snapshot.usage
        text = format_panel_label(
            usage.session.percentage,
            usage.weekly.percentage,
            self._codex_headline_percentage(),
        )
        self._indicator.set_label(text, "100% · 100% | Cx 100%")

    def _set_icon(
        self, session: float | None, weekly: float | None, codex: float | None = None
    ) -> None:
        # Alternating file names force the panel to reload the changed image.
        self._icon_slot ^= 1
        name = f"usage-{self._icon_slot}"
        try:
            render_icon(self._icon_dir / f"{name}.png", session, weekly, codex)
        except (OSError, MemoryError):
            self._indicator.set_icon_full("dialog-information", "Claude Usage")
            return
        self._indicator.set_icon_full(name, "Claude Usage")

    # ------------------------------------------------------- notifications

    def _init_notifications(self):
        try:
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify

            Notify.init("Claude Usage Monitor")
            return Notify
        except (ValueError, ImportError):
            return None

    def _maybe_notify(self, usage: UsageData) -> None:
        if self._notify is None or not self._config.notify_on_thresholds:
            return

        for key, label, window in (
            ("session", "5-Stunden-Fenster", usage.session),
            ("weekly", "7-Tage-Fenster", usage.weekly),
        ):
            level = self._threshold_level(window.percentage)
            if level == self._notified_levels.get(key):
                continue
            self._notified_levels[key] = level
            if level == "normal":
                continue
            urgency = "kritisch" if level == "critical" else "hoch"
            self._show_notification(
                f"Claude {label}: {window.percentage:.0f}%",
                f"Auslastung {urgency}. Reset in {format_countdown(window.seconds_until_reset)}.",
            )

    @staticmethod
    def _threshold_level(percentage: float) -> str:
        if percentage >= CRITICAL_THRESHOLD:
            return "critical"
        if percentage >= WARN_THRESHOLD:
            return "warn"
        return "normal"

    def _show_notification(self, title: str, body: str) -> None:
        try:
            notification = self._notify.Notification.new(title, body, "dialog-warning")
            notification.show()
        except GLib.Error:
            pass

    # ----------------------------------------------------------------- run

    def run(self) -> int:
        self._icon_dir.mkdir(parents=True, exist_ok=True)
        self._set_icon(None, None)
        self._poller.start()
        GLib.timeout_add_seconds(MENU_TICK_SECONDS, self._tick)
        Gtk.main()
        return 0
