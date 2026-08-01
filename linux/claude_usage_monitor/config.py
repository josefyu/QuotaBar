"""User configuration, persisted as JSON under XDG_CONFIG_HOME."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

ALLOWED_INTERVALS = (60, 120, 300, 600, 900)
WARN_THRESHOLD = 80.0
CRITICAL_THRESHOLD = 95.0


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "claude-usage-monitor"


CONFIG_PATH = _config_dir() / "config.json"


@dataclass
class Config:
    poll_interval_seconds: int = 300
    show_panel_label: bool = True
    notify_on_thresholds: bool = True

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(raw, dict):
            return cls()

        known = {f.name for f in fields(cls)}
        values = {key: value for key, value in raw.items() if key in known}
        config = cls(**values)
        if config.poll_interval_seconds not in ALLOWED_INTERVALS:
            config.poll_interval_seconds = cls.poll_interval_seconds
        return config

    def save(self, path: Path = CONFIG_PATH) -> None:
        """Persist the config; failures are non-fatal for a tray widget."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
