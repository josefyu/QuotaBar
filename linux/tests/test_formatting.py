import pytest

from claude_usage_monitor.formatting import (
    format_countdown,
    format_panel_label,
    format_percentage,
)


@pytest.mark.unit
def test_panel_label_uses_the_source_prefix():
    assert format_panel_label("Cl", 80.4, 39.6) == "Cl 80% · 40%"
    assert format_panel_label("Cx", 20.0, 12.0) == "Cx 20% · 12%"


@pytest.mark.unit
def test_panel_label_marks_a_missing_window():
    assert format_panel_label("Cx", None, 12.0) == "Cx — · 12%"
    assert format_panel_label("Cx", None, None) == "Cx — · —"


@pytest.mark.unit
def test_percentage_rounds_to_whole_numbers():
    assert format_percentage(0.0) == "0%"
    assert format_percentage(99.5) == "100%"
    assert format_percentage(None) == "—"


@pytest.mark.unit
@pytest.mark.parametrize(
    "seconds,expected",
    [
        (None, "unbekannt"),
        (0, "jetzt"),
        (-5, "jetzt"),
        (90, "1m"),
        (3 * 3600 + 5 * 60, "3h 05m"),
        (2 * 86400 + 4 * 3600, "2d 4h"),
    ],
)
def test_countdown_formats(seconds, expected):
    assert format_countdown(seconds) == expected
