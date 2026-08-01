"""Entry point: tray widget by default, terminal modes on request."""

from __future__ import annotations

import argparse
import sys

from .config import ALLOWED_INTERVALS, Config


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="claude-usage-monitor",
        description="Zeigt die Auslastung des 5-Stunden- und 7-Tage-Fensters von Claude Code.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Einmalig im Terminal ausgeben")
    mode.add_argument("--watch", action="store_true", help="Im Terminal laufend aktualisieren")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON (nur mit --once)")
    parser.add_argument(
        "--interval",
        type=int,
        choices=ALLOWED_INTERVALS,
        help="Abfrageintervall in Sekunden (ueberschreibt die Konfiguration)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    config = Config.load()
    if args.interval:
        config.poll_interval_seconds = args.interval

    if args.once or args.json:
        from .cli import run_once

        return run_once(as_json=args.json)

    if args.watch:
        from .cli import run_watch

        return run_watch(config.poll_interval_seconds)

    return _run_tray(config)


def _run_tray(config: Config) -> int:
    from .tray import TrayApp, load_indicator_module

    appindicator = load_indicator_module()
    if appindicator is None:
        print(
            "AppIndicator-Bindings fehlen. Installieren mit:\n"
            "  sudo apt install gir1.2-ayatanaappindicator3-0.1\n"
            "Bis dahin funktioniert der Terminal-Modus: claude-usage-monitor --watch",
            file=sys.stderr,
        )
        return 2

    return TrayApp(appindicator, config).run()


if __name__ == "__main__":
    sys.exit(main())
