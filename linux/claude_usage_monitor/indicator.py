"""One panel indicator: its icon, its menu and its notification state.

The class is instantiated once per usage source. Everything that differs
between Claude and Codex lives in :class:`IndicatorSpec`; the shared settings
and the poller stay with the coordinator in :mod:`tray`, which reaches the
indicator through :class:`IndicatorActions`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .api import UsageWindow  # noqa: E402
from .config import ALLOWED_INTERVALS, CRITICAL_THRESHOLD, WARN_THRESHOLD  # noqa: E402
from .formatting import format_countdown, format_panel_label, format_percentage  # noqa: E402
from .icon import INNER, OUTER, render_error, render_rings  # noqa: E402

WINDOW_LABELS = (("5h", "5-Stunden-Fenster"), ("7d", "7-Tage-Fenster"))


@dataclass(frozen=True)
class IndicatorSpec:
    """Everything that distinguishes one source's indicator from another's."""

    app_id: str
    source: str  # shown in titles and notifications, e.g. "Claude"
    glyph: str  # single letter drawn into the icon core
    label_prefix: str  # panel text prefix, e.g. "Cl"
    icon_basename: str  # icon file stem; must be unique per indicator


@dataclass(frozen=True)
class IndicatorActions:
    """Menu callbacks. All of them act on state the coordinator owns."""

    refresh: Callable[[], None]
    set_interval: Callable[[int], None]
    set_show_label: Callable[[bool], None]
    set_notify: Callable[[bool], None]
    quit: Callable[[], None]


@dataclass(frozen=True)
class MenuState:
    """Initial state of the shared settings, mirrored into every menu."""

    poll_interval_seconds: int
    show_panel_label: bool
    notify_on_thresholds: bool
    notify_available: bool


@dataclass(frozen=True)
class Notification:
    title: str
    body: str


def threshold_level(percentage: float) -> str:
    if percentage >= CRITICAL_THRESHOLD:
        return "critical"
    if percentage >= WARN_THRESHOLD:
        return "warn"
    return "normal"


class UsageIndicator:
    """A single tray icon with a 5h ring, a 7d ring and its own menu."""

    def __init__(
        self,
        appindicator,
        spec: IndicatorSpec,
        actions: IndicatorActions,
        state: MenuState,
        icon_dir: Path,
    ) -> None:
        self._appindicator = appindicator
        self._spec = spec
        self._actions = actions
        self._icon_dir = icon_dir
        self._icon_slot = 0
        self._show_label = state.show_panel_label
        self._syncing = False
        self._notified_levels: dict[str, str] = {}

        self._indicator = appindicator.Indicator.new(
            spec.app_id,
            "dialog-information",
            appindicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self._indicator.set_icon_theme_path(str(icon_dir))
        self._build_menu(state)
        self.show_loading()

    # ---------------------------------------------------------------- menu

    def _build_menu(self, state: MenuState) -> None:
        self._menu = Gtk.Menu()

        self._window_items = []
        for short_label, _ in WINDOW_LABELS:
            item = Gtk.MenuItem(label=f"{short_label}: —")
            item.set_sensitive(False)
            self._window_items.append(item)
            self._menu.append(item)

        self._status_item = Gtk.MenuItem(label="Lade …")
        self._status_item.set_sensitive(False)
        self._menu.append(self._status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        refresh_item = Gtk.MenuItem(label="Jetzt aktualisieren")
        refresh_item.connect("activate", lambda _item: self._actions.refresh())
        self._menu.append(refresh_item)

        self._menu.append(self._build_interval_item(state.poll_interval_seconds))

        self._label_item = Gtk.CheckMenuItem(label="Text im Panel")
        self._label_item.set_active(state.show_panel_label)
        self._label_item.connect("toggled", self._on_toggle_label)
        self._menu.append(self._label_item)

        self._notify_item = Gtk.CheckMenuItem(label="Benachrichtigungen")
        self._notify_item.set_active(state.notify_on_thresholds)
        self._notify_item.set_sensitive(state.notify_available)
        self._notify_item.connect("toggled", self._on_toggle_notify)
        self._menu.append(self._notify_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Beenden")
        quit_item.connect("activate", lambda _item: self._actions.quit())
        self._menu.append(quit_item)

        self._menu.show_all()
        self._indicator.set_menu(self._menu)

    def _build_interval_item(self, selected_seconds: int) -> Gtk.MenuItem:
        parent = Gtk.MenuItem(label="Aktualisierungsintervall")
        submenu = Gtk.Menu()
        group: list[Gtk.RadioMenuItem] = []
        self._interval_items: dict[int, Gtk.RadioMenuItem] = {}

        for seconds in ALLOWED_INTERVALS:
            item = Gtk.RadioMenuItem(label=f"{seconds // 60} min")
            if group:
                item.join_group(group[0])
            group.append(item)
            item.set_active(seconds == selected_seconds)
            item.connect("toggled", self._on_interval_selected, seconds)
            submenu.append(item)
            self._interval_items[seconds] = item

        parent.set_submenu(submenu)
        return parent

    # ------------------------------------------------------------ handlers

    def _on_interval_selected(self, item: Gtk.RadioMenuItem, seconds: int) -> None:
        if self._syncing or not item.get_active():
            return
        self._actions.set_interval(seconds)

    def _on_toggle_label(self, item: Gtk.CheckMenuItem) -> None:
        if self._syncing:
            return
        self._actions.set_show_label(item.get_active())

    def _on_toggle_notify(self, item: Gtk.CheckMenuItem) -> None:
        if self._syncing:
            return
        self._actions.set_notify(item.get_active())

    def sync_state(self, state: MenuState) -> None:
        """Mirror settings changed in another indicator's menu."""
        self._show_label = state.show_panel_label
        self._syncing = True
        try:
            self._label_item.set_active(state.show_panel_label)
            self._notify_item.set_active(state.notify_on_thresholds)
            item = self._interval_items.get(state.poll_interval_seconds)
            if item is not None:
                item.set_active(True)
        finally:
            self._syncing = False

    # ------------------------------------------------------------- updates

    def set_active(self, visible: bool) -> None:
        status = (
            self._appindicator.IndicatorStatus.ACTIVE
            if visible
            else self._appindicator.IndicatorStatus.PASSIVE
        )
        self._indicator.set_status(status)

    def update(
        self,
        session: UsageWindow | None,
        weekly: UsageWindow | None,
        fetched_at: datetime | None,
    ) -> list[Notification]:
        """Redraw icon, menu and panel text; returns pending threshold alerts."""
        for item, (short_label, _), window in zip(
            self._window_items, WINDOW_LABELS, (session, weekly)
        ):
            item.set_label(self._window_row(short_label, window))

        stamp = fetched_at.astimezone().strftime("%H:%M:%S") if fetched_at else "—"
        self._status_item.set_label(f"Stand: {stamp}")

        session_percentage = session.percentage if session else None
        weekly_percentage = weekly.percentage if weekly else None
        self._indicator.set_title(
            f"{self._spec.source} Usage — "
            f"5h {format_percentage(session_percentage)}, "
            f"7d {format_percentage(weekly_percentage)}"
        )
        self._render(lambda path: render_rings(
            path,
            ((OUTER, session_percentage), (INNER, weekly_percentage)),
            self._spec.glyph,
        ))
        self._apply_panel_label(session_percentage, weekly_percentage)
        return self._threshold_notifications(session, weekly)

    def show_error(self, message: str) -> None:
        self._reset_rows("nicht verfuegbar", message)
        self._indicator.set_title(f"{self._spec.source} Usage — Fehler")
        self._render(lambda path: render_error(path, self._spec.glyph))

    def show_loading(self) -> None:
        """Empty rings without the fault marker, used until the first poll."""
        self._reset_rows("—", "Lade …")
        self._indicator.set_title(f"{self._spec.source} Usage")
        self._render(lambda path: render_rings(
            path, ((OUTER, None), (INNER, None)), self._spec.glyph
        ))

    def _reset_rows(self, value: str, status: str) -> None:
        for item, (short_label, _) in zip(self._window_items, WINDOW_LABELS):
            item.set_label(f"{short_label}: {value}")
        self._status_item.set_label(status)
        self._indicator.set_label("", "")

    @staticmethod
    def _window_row(short_label: str, window: UsageWindow | None) -> str:
        if window is None:
            return f"{short_label}: —"
        return (
            f"{short_label}: {window.percentage:.0f}%  ·  Reset in "
            f"{format_countdown(window.seconds_until_reset)}"
        )

    def _apply_panel_label(
        self, session_percentage: float | None, weekly_percentage: float | None
    ) -> None:
        if not self._show_label:
            self._indicator.set_label("", "")
            return
        text = format_panel_label(
            self._spec.label_prefix, session_percentage, weekly_percentage
        )
        self._indicator.set_label(text, f"{self._spec.label_prefix} 100% · 100%")

    def _render(self, draw: Callable[[Path], Path]) -> None:
        # Alternating file names force the panel to reload the changed image.
        self._icon_slot ^= 1
        name = f"{self._spec.icon_basename}-{self._icon_slot}"
        try:
            draw(self._icon_dir / f"{name}.png")
        except (OSError, MemoryError):
            self._indicator.set_icon_full("dialog-information", self._spec.source)
            return
        self._indicator.set_icon_full(name, self._spec.source)

    # ------------------------------------------------------- notifications

    def _threshold_notifications(
        self, session: UsageWindow | None, weekly: UsageWindow | None
    ) -> list[Notification]:
        """Alerts for windows that just entered a higher severity band.

        Levels are tracked even while notifications are switched off, so
        re-enabling them does not replay every crossing that happened since.
        """
        pending: list[Notification] = []
        for (short_label, long_label), window in zip(WINDOW_LABELS, (session, weekly)):
            if window is None:
                continue
            level = threshold_level(window.percentage)
            if level == self._notified_levels.get(short_label):
                continue
            self._notified_levels[short_label] = level
            if level == "normal":
                continue
            urgency = "kritisch" if level == "critical" else "hoch"
            pending.append(
                Notification(
                    title=f"{self._spec.source} {long_label}: {window.percentage:.0f}%",
                    body=(
                        f"Auslastung {urgency}. Reset in "
                        f"{format_countdown(window.seconds_until_reset)}."
                    ),
                )
            )
        return pending
