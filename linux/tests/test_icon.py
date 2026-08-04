import pytest

from claude_usage_monitor.icon import INNER, OUTER, render_error, render_rings

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _read(path):
    data = path.read_bytes()
    assert data.startswith(PNG_MAGIC)
    return data


@pytest.mark.unit
def test_render_rings_writes_a_png(tmp_path):
    path = render_rings(
        tmp_path / "nested" / "claude-0.png",
        ((OUTER, 42.0), (INNER, 91.0)),
        "C",
    )
    assert path.exists()
    _read(path)


@pytest.mark.unit
def test_render_rings_accepts_missing_windows(tmp_path):
    path = render_rings(tmp_path / "codex.png", ((OUTER, None), (INNER, 5.0)), "X")
    _read(path)


@pytest.mark.unit
def test_render_rings_clamps_out_of_range_values(tmp_path):
    path = render_rings(tmp_path / "clamped.png", ((OUTER, -20.0), (INNER, 250.0)), "C")
    _read(path)


@pytest.mark.unit
def test_error_icon_differs_from_the_gauge(tmp_path):
    gauge = render_rings(tmp_path / "gauge.png", ((OUTER, None), (INNER, None)), "X")
    error = render_error(tmp_path / "error.png", "X")
    assert _read(gauge) != _read(error)


@pytest.mark.unit
def test_glyph_changes_the_image(tmp_path):
    claude = render_rings(tmp_path / "c.png", ((OUTER, 50.0), (INNER, 50.0)), "C")
    codex = render_rings(tmp_path / "x.png", ((OUTER, 50.0), (INNER, 50.0)), "X")
    assert _read(claude) != _read(codex)
