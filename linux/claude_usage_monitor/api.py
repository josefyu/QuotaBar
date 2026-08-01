"""Anthropic usage lookup.

Primary source is the OAuth usage endpoint. When it is unavailable the
Messages API is called with a 1-token request and the unified rate-limit
response headers are read instead — same fallback chain as the upstream
Windows widget.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from .credentials import AuthRequired

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"
OAUTH_BETA = "oauth-2025-04-20"
ANTHROPIC_VERSION = "2023-06-01"
USER_AGENT = "claude-usage-monitor-linux/1.0"
REQUEST_TIMEOUT_SECONDS = 20

MODEL_FALLBACK_CHAIN = (
    "claude-3-haiku-20240307",
    "claude-haiku-4-5-20251001",
)


class UsageError(Exception):
    """Usage could not be retrieved."""


@dataclass(frozen=True)
class UsageWindow:
    percentage: float
    resets_at: datetime | None

    @property
    def seconds_until_reset(self) -> float | None:
        if self.resets_at is None:
            return None
        return (self.resets_at - datetime.now(timezone.utc)).total_seconds()


@dataclass(frozen=True)
class UsageData:
    session: UsageWindow  # rolling 5 hour window
    weekly: UsageWindow  # rolling 7 day window
    fetched_at: datetime


def _parse_iso8601(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unix_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _request(url: str, token: str, *, body: bytes | None = None, extra_headers: dict | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": OAUTH_BETA,
        "User-Agent": USER_AGENT,
    }
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")


def _fetch_usage_endpoint(token: str) -> UsageData | None:
    """Returns None when the endpoint is unusable so the caller can fall back."""
    try:
        with urllib.request.urlopen(_request(USAGE_URL, token), timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthRequired(f"Usage-Endpoint lehnt Token ab (HTTP {exc.code})") from exc
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return UsageData(
        session=_bucket(payload.get("five_hour")),
        weekly=_bucket(payload.get("seven_day")),
        fetched_at=datetime.now(timezone.utc),
    )


def _bucket(raw: object) -> UsageWindow:
    if not isinstance(raw, dict):
        return UsageWindow(percentage=0.0, resets_at=None)
    utilization = raw.get("utilization")
    percentage = float(utilization) if isinstance(utilization, (int, float)) else 0.0
    return UsageWindow(percentage=percentage, resets_at=_parse_iso8601(raw.get("resets_at")))


def _fetch_via_messages(token: str) -> UsageData:
    """Read the unified rate-limit headers off a minimal Messages request."""
    last_error: Exception | None = None

    for model in MODEL_FALLBACK_CHAIN:
        body = json.dumps(
            {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}
        ).encode("utf-8")
        request = _request(
            MESSAGES_URL,
            token,
            body=body,
            extra_headers={
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                headers = resp.headers
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthRequired(f"Messages-API lehnt Token ab (HTTP {exc.code})") from exc
            # Rate-limit headers are present on error responses too.
            headers = exc.headers
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            continue

        parsed = _from_rate_limit_headers(headers)
        if parsed is not None:
            return parsed

    raise UsageError(f"Kein Usage-Wert ermittelbar ({last_error or 'keine Rate-Limit-Header'})")


def _from_rate_limit_headers(headers) -> UsageData | None:
    if headers is None:
        return None

    five = headers.get("anthropic-ratelimit-unified-5h-utilization")
    seven = headers.get("anthropic-ratelimit-unified-7d-utilization")
    if five is None and seven is None:
        return None

    def ratio(value: str | None) -> float:
        try:
            # Headers report a 0..1 ratio, the endpoint reports percent.
            return float(value) * 100.0
        except (TypeError, ValueError):
            return 0.0

    return UsageData(
        session=UsageWindow(
            percentage=ratio(five),
            resets_at=_unix_to_datetime(headers.get("anthropic-ratelimit-unified-5h-reset")),
        ),
        weekly=UsageWindow(
            percentage=ratio(seven),
            resets_at=_unix_to_datetime(headers.get("anthropic-ratelimit-unified-7d-reset")),
        ),
        fetched_at=datetime.now(timezone.utc),
    )


def fetch_usage(token: str) -> UsageData:
    """Fetch usage, preferring the dedicated endpoint over the Messages probe."""
    data = _fetch_usage_endpoint(token)
    if data is None:
        return _fetch_via_messages(token)

    if data.session.resets_at is not None and data.weekly.resets_at is not None:
        return data

    # Endpoint answered but without reset timestamps — fill them in.
    try:
        fallback = _fetch_via_messages(token)
    except (UsageError, AuthRequired):
        return data

    return UsageData(
        session=UsageWindow(data.session.percentage, data.session.resets_at or fallback.session.resets_at),
        weekly=UsageWindow(data.weekly.percentage, data.weekly.resets_at or fallback.weekly.resets_at),
        fetched_at=data.fetched_at,
    )
