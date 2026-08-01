"""Codex (ChatGPT) usage lookup.

Reads the Codex CLI credentials and queries the same endpoint the upstream
Windows widget uses. Codex is optional: when no credential file exists the
monitor simply omits the Codex section.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .api import UsageWindow

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
USER_AGENT = "codex-cli"
REQUEST_TIMEOUT_SECONDS = 20
CLI_REFRESH_TIMEOUT_SECONDS = 120

# A window at or below this length is treated as the short (session) window,
# anything longer as the long (weekly) window. The API labels its buckets only
# as primary/secondary, and which is which differs per account.
SHORT_WINDOW_MAX_SECONDS = 6 * 3600


class CodexUnavailable(Exception):
    """No Codex credentials on this machine — not an error worth showing."""


class CodexError(Exception):
    """Codex is configured but the usage lookup failed."""


@dataclass(frozen=True)
class CodexUsage:
    short: UsageWindow | None
    long: UsageWindow | None
    fetched_at: datetime


@dataclass(frozen=True)
class CodexTokens:
    access_token: str
    account_id: str | None


def auth_path() -> Path:
    home = os.environ.get("CODEX_HOME")
    base = Path(home) if home else (Path.home() / ".codex")
    return base / "auth.json"


def is_configured() -> bool:
    return auth_path().is_file()


def read_tokens() -> CodexTokens:
    path = auth_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CodexUnavailable(f"Keine Codex-Credentials unter {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexError(f"Codex-Credentials unlesbar: {exc}") from exc

    tokens = raw.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexUnavailable("Codex nicht eingeloggt (Feld 'tokens' fehlt)")

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise CodexUnavailable("Codex nicht eingeloggt (kein access_token)")

    account_id = tokens.get("account_id")
    return CodexTokens(
        access_token=access_token,
        account_id=account_id if isinstance(account_id, str) and account_id else None,
    )


def watch_signature() -> str:
    try:
        stat = auth_path().stat()
    except OSError:
        return "missing"
    return f"present|{stat.st_size}|{int(stat.st_mtime)}"


def cli_refresh_token() -> bool:
    """Make the Codex CLI refresh its OAuth token by running a no-op prompt."""
    executable = shutil.which("codex")
    if executable is None:
        return False
    try:
        subprocess.run(
            [executable, "exec", "."],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CLI_REFRESH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def _window(raw: object) -> tuple[UsageWindow, float] | None:
    """Returns the parsed window plus its length in seconds."""
    if not isinstance(raw, dict):
        return None
    used = raw.get("used_percent")
    if not isinstance(used, (int, float)):
        return None

    reset_at = raw.get("reset_at")
    resets_at = None
    if isinstance(reset_at, (int, float)) and reset_at > 0:
        try:
            resets_at = datetime.fromtimestamp(float(reset_at), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            resets_at = None

    length = raw.get("limit_window_seconds")
    length_seconds = float(length) if isinstance(length, (int, float)) else 0.0
    return UsageWindow(percentage=float(used), resets_at=resets_at), length_seconds


def _request(tokens: CodexTokens) -> urllib.request.Request:
    headers = {
        "Authorization": f"Bearer {tokens.access_token}",
        "User-Agent": USER_AGENT,
    }
    if tokens.account_id:
        headers["ChatGPT-Account-Id"] = tokens.account_id
    return urllib.request.Request(USAGE_URL, headers=headers, method="GET")


def _call(tokens: CodexTokens) -> dict:
    try:
        with urllib.request.urlopen(_request(tokens), timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise PermissionError(f"Codex-Token abgelehnt (HTTP {exc.code})") from exc
        raise CodexError(f"Codex-Endpoint HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CodexError(f"Codex-Abfrage fehlgeschlagen: {exc}") from exc

    if not isinstance(payload, dict):
        raise CodexError("Codex-Antwort hat unerwartetes Format")
    return payload


def fetch_usage() -> CodexUsage:
    """Fetch Codex usage, refreshing the token once on an auth rejection."""
    tokens = read_tokens()
    try:
        payload = _call(tokens)
    except PermissionError:
        if not cli_refresh_token():
            raise CodexError("Codex-Token abgelaufen und 'codex' CLI nicht ausfuehrbar") from None
        payload = _call(read_tokens())

    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        raise CodexError("Codex-Antwort enthaelt kein 'rate_limit'")

    short: UsageWindow | None = None
    long: UsageWindow | None = None
    for key in ("primary_window", "secondary_window"):
        parsed = _window(rate_limit.get(key))
        if parsed is None:
            continue
        window, length_seconds = parsed
        if 0 < length_seconds <= SHORT_WINDOW_MAX_SECONDS:
            short = window
        else:
            long = window

    if short is None and long is None:
        raise CodexError("Codex meldet keine Limit-Fenster")

    return CodexUsage(short=short, long=long, fetched_at=datetime.now(timezone.utc))
