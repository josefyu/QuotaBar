"""Background polling thread producing immutable usage snapshots."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

from . import codex, credentials
from .api import UsageData, UsageError, fetch_usage
from .codex import CodexError, CodexUnavailable, CodexUsage
from .credentials import AuthRequired, CredentialError

# The credentials file is checked far more often than the API is called, so an
# externally refreshed token is picked up quickly without extra API traffic.
CREDENTIAL_CHECK_SECONDS = 15


def _watch_signature() -> str:
    """Combined fingerprint of all credential files the monitor reads."""
    return f"{credentials.watch_signature()}|{codex.watch_signature()}"


@dataclass(frozen=True)
class Snapshot:
    """Result of one poll. Claude and Codex succeed or fail independently."""

    usage: UsageData | None
    error: str | None
    needs_login: bool
    at: datetime
    codex: CodexUsage | None = None
    codex_error: str | None = None

    def with_codex(self, usage: CodexUsage | None, error: str | None) -> "Snapshot":
        return replace(self, codex=usage, codex_error=error)

    @classmethod
    def success(cls, usage: UsageData) -> "Snapshot":
        return cls(usage=usage, error=None, needs_login=False, at=datetime.now(timezone.utc))

    @classmethod
    def failure(cls, message: str, *, needs_login: bool = False) -> "Snapshot":
        return cls(usage=None, error=message, needs_login=needs_login, at=datetime.now(timezone.utc))


def codex_is_visible(snapshot: Snapshot) -> bool:
    """Codex earns a panel slot as soon as it reports either data or a problem."""
    return snapshot.codex is not None or snapshot.codex_error is not None


def _poll_claude() -> Snapshot:
    try:
        creds = credentials.get_valid_credentials()
    except AuthRequired as exc:
        return Snapshot.failure(str(exc), needs_login=True)
    except CredentialError as exc:
        return Snapshot.failure(str(exc))

    try:
        return Snapshot.success(fetch_usage(creds.access_token))
    except AuthRequired as exc:
        return Snapshot.failure(str(exc), needs_login=True)
    except UsageError as exc:
        return Snapshot.failure(str(exc))
    except Exception as exc:  # network stacks raise a wide range of errors
        return Snapshot.failure(f"Unerwarteter Fehler: {exc}")


def _poll_codex() -> tuple[CodexUsage | None, str | None]:
    """Returns (usage, error). Both None when Codex is not set up at all."""
    if not codex.is_configured():
        return None, None
    try:
        return codex.fetch_usage(), None
    except CodexUnavailable:
        return None, None
    except CodexError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Unerwarteter Codex-Fehler: {exc}"


def poll_once() -> Snapshot:
    """Single blocking poll of every configured source. Never raises."""
    snapshot = _poll_claude()
    codex_usage, codex_error = _poll_codex()
    return snapshot.with_codex(codex_usage, codex_error)


class Poller:
    """Polls in a daemon thread and hands snapshots to a callback."""

    def __init__(self, on_snapshot: Callable[[Snapshot], None], interval_seconds: int) -> None:
        self._on_snapshot = on_snapshot
        self._interval = interval_seconds
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._credential_signature = _watch_signature()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="usage-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wakeup.set()

    def refresh_now(self) -> None:
        self._wakeup.set()

    def set_interval(self, seconds: int) -> None:
        with self._lock:
            self._interval = seconds
        self._wakeup.set()

    @property
    def interval(self) -> int:
        with self._lock:
            return self._interval

    def _run(self) -> None:
        while not self._stop.is_set():
            self._on_snapshot(poll_once())
            if not self._sleep_until_due():
                return

    def _sleep_until_due(self) -> bool:
        """Sleep in short slices; returns False when the poller was stopped."""
        waited = 0
        while waited < self.interval:
            slice_seconds = min(CREDENTIAL_CHECK_SECONDS, self.interval - waited)
            if self._wakeup.wait(slice_seconds):
                self._wakeup.clear()
                return not self._stop.is_set()
            waited += slice_seconds

            signature = _watch_signature()
            if signature != self._credential_signature:
                self._credential_signature = signature
                return True
        return True
