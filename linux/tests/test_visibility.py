from datetime import datetime, timezone

import pytest

from claude_usage_monitor.api import UsageWindow
from claude_usage_monitor.codex import CodexUsage
from claude_usage_monitor.poller import Snapshot, codex_is_visible


def _snapshot(codex=None, codex_error=None) -> Snapshot:
    return Snapshot(
        usage=None,
        error="offline",
        needs_login=False,
        at=datetime.now(timezone.utc),
        codex=codex,
        codex_error=codex_error,
    )


def _codex_usage() -> CodexUsage:
    return CodexUsage(
        short=UsageWindow(percentage=12.0, resets_at=None),
        long=None,
        fetched_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
def test_hidden_when_codex_is_not_set_up():
    assert codex_is_visible(_snapshot()) is False


@pytest.mark.unit
def test_visible_when_codex_reports_usage():
    assert codex_is_visible(_snapshot(codex=_codex_usage())) is True


@pytest.mark.unit
def test_visible_when_codex_reports_an_error():
    assert codex_is_visible(_snapshot(codex_error="Token abgelaufen")) is True


@pytest.mark.unit
def test_visible_when_codex_reports_usage_and_an_error():
    snapshot = _snapshot(codex=_codex_usage(), codex_error="teilweise")
    assert codex_is_visible(snapshot) is True
