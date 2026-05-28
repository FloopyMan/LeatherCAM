"""Tests for the SVG importer."""

from __future__ import annotations

import math
from io import StringIO

import pytest

from leathercam.vector import Polyline, load_svg


def _svg(body: str, width_mm: float = 100.0, height_mm: float = 50.0) -> StringIO:
    doc = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm}mm" height="{height_mm}mm" '
        f'viewBox="0 0 {width_mm} {height_mm}">{body}</svg>'
    )
    return StringIO(doc)


def test_load_rect_yields_one_closed_polyline_in_mm() -> None:
    polys = load_svg(_svg('<rect x="10" y="10" width="80" height="30"/>'))
    assert len(polys) == 1
    poly = polys[0]
    assert poly.closed is True
    xs = [p[0] for p in poly.points]
    ys = [p[1] for p in poly.points]
    assert min(xs) == pytest.approx(10.0, abs=1e-3)
    assert max(xs) == pytest.approx(90.0, abs=1e-3)
    assert min(ys) == pytest.approx(10.0, abs=1e-3)
    assert max(ys) == pytest.approx(40.0, abs=1e-3)


def test_y_axis_is_flipped_so_top_left_becomes_high_y() -> None:
    polys = load_svg(_svg('<rect x="0" y="0" width="10" height="10"/>'))
    poly = polys[0]
    ys = [p[1] for p in poly.points]
    assert max(ys) == pytest.approx(50.0, abs=1e-3)
    assert min(ys) == pytest.approx(40.0, abs=1e-3)


def test_circle_is_approximated_within_tolerance() -> None:
    polys = load_svg(
        _svg('<circle cx="50" cy="25" r="10"/>'),
        max_segment_mm=0.05,
    )
    poly = polys[0]
    cx, cy_inverted = 50.0, 50.0 - 25.0
    for x, y in poly.points:
        r = math.hypot(x - cx, y - cy_inverted)
        assert r == pytest.approx(10.0, abs=0.05)


def test_smaller_max_segment_produces_more_points() -> None:
    coarse = load_svg(_svg('<circle cx="50" cy="25" r="10"/>'), max_segment_mm=1.0)
    fine = load_svg(_svg('<circle cx="50" cy="25" r="10"/>'), max_segment_mm=0.05)
    assert len(fine[0].points) > len(coarse[0].points) * 3


def test_polyline_element_is_open() -> None:
    polys = load_svg(_svg('<polyline points="10,10 20,10 20,20"/>'))
    assert len(polys) == 1
    assert polys[0].closed is False
    assert len(polys[0].points) == 3


def test_polygon_element_is_closed() -> None:
    polys = load_svg(_svg('<polygon points="10,10 20,10 20,20"/>'))
    assert len(polys) == 1
    assert polys[0].closed is True


def test_path_with_multiple_subpaths_yields_multiple_polylines() -> None:
    body = '<path d="M 10,10 L 30,10 L 30,20 Z M 50,10 L 70,10 L 70,20 Z"/>'
    polys = load_svg(_svg(body))
    assert len(polys) == 2
    assert all(p.closed for p in polys)


def test_line_element_is_open_two_point_polyline() -> None:
    polys = load_svg(_svg('<line x1="0" y1="0" x2="10" y2="0"/>'))
    assert len(polys) == 1
    assert polys[0].closed is False
    assert len(polys[0].points) == 2


def test_returns_polyline_instances() -> None:
    polys = load_svg(_svg('<rect x="0" y="0" width="5" height="5"/>'))
    assert all(isinstance(p, Polyline) for p in polys)


def test_rejects_non_positive_max_segment() -> None:
    with pytest.raises(ValueError):
        load_svg(_svg('<rect x="0" y="0" width="5" height="5"/>'), max_segment_mm=0.0)


def test_unitless_svg_treated_as_px_at_96dpi() -> None:
    doc = StringIO(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="96" height="96" viewBox="0 0 96 96">'
        '<line x1="0" y1="48" x2="96" y2="48"/></svg>'
    )
    polys = load_svg(doc)
    poly = polys[0]
    xs = [p[0] for p in poly.points]
    assert max(xs) == pytest.approx(25.4, abs=1e-3)
