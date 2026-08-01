"""Reading and refreshing the local Claude Code OAuth credentials.

Mirrors the credential handling of the upstream Windows widget:
the token lives in ``~/.claude/.credentials.json`` and is refreshed by
invoking the Claude CLI with a minimal prompt, which makes the CLI perform
its own OAuth refresh and rewrite the file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# Refresh a bit before the real expiry so a poll never races the deadline.
EXPIRY_MARGIN_SECONDS = 60
CLI_REFRESH_TIMEOUT_SECONDS = 90


class CredentialError(Exception):
    """Credentials are missing, unreadable or beyond repair."""


class AuthRequired(CredentialError):
    """The user has to log in again via ``claude`` — no refresh can fix this."""


@dataclass(frozen=True)
class Credentials:
    access_token: str
    expires_at: float  # POSIX seconds
    subscription_type: str | None
    rate_limit_tier: str | None

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() >= (self.expires_at - EXPIRY_MARGIN_SECONDS)


def read_credentials(path: Path = CREDENTIALS_PATH) -> Credentials:
    """Load credentials from disk. Raises CredentialError on any problem."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CredentialError(f"Credentials nicht gefunden: {path}") from exc
    except PermissionError as exc:
        raise CredentialError(f"Keine Leserechte auf {path}") from exc
    except json.JSONDecodeError as exc:
        raise CredentialError(f"Credentials-Datei ist kein gueltiges JSON: {exc}") from exc

    oauth = raw.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        raise CredentialError("Feld 'claudeAiOauth' fehlt in den Credentials")

    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token:
        raise AuthRequired("Kein accessToken vorhanden — bitte 'claude' neu einloggen")

    expires_at_ms = oauth.get("expiresAt")
    expires_at = float(expires_at_ms) / 1000.0 if isinstance(expires_at_ms, (int, float)) else 0.0

    return Credentials(
        access_token=token,
        expires_at=expires_at,
        subscription_type=oauth.get("subscriptionType"),
        rate_limit_tier=oauth.get("rateLimitTier"),
    )


def watch_signature(path: Path = CREDENTIALS_PATH) -> str:
    """Cheap fingerprint used to detect an externally refreshed token file."""
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"present|{stat.st_size}|{int(stat.st_mtime)}"


def _claude_executable() -> str | None:
    explicit = os.environ.get("CLAUDE_BIN")
    if explicit and Path(explicit).exists():
        return explicit
    return shutil.which("claude") or _fallback_claude_path()


def _fallback_claude_path() -> str | None:
    candidate = Path.home() / ".local" / "bin" / "claude"
    return str(candidate) if candidate.exists() else None


def cli_refresh_token() -> bool:
    """Force the Claude CLI to refresh its OAuth token.

    Returns True when the CLI ran; the caller still has to re-read the file to
    find out whether the refresh actually produced a fresh token.
    """
    executable = _claude_executable()
    if executable is None:
        return False

    env = dict(os.environ)
    # The CLI refuses the nested-session shortcut when these are set.
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    try:
        subprocess.run(
            [executable, "-p", "."],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CLI_REFRESH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def get_valid_credentials() -> Credentials:
    """Return usable credentials, refreshing via the CLI when expired."""
    creds = read_credentials()
    if not creds.is_expired:
        return creds

    if not cli_refresh_token():
        raise AuthRequired("Token abgelaufen und 'claude' CLI nicht ausfuehrbar")

    refreshed = read_credentials()
    if refreshed.is_expired:
        raise AuthRequired("Token nach Refresh weiterhin abgelaufen — bitte neu einloggen")
    return refreshed
