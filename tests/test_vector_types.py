"""Tests for the Polyline data type."""

from __future__ import annotations

import math

import pytest

from leathercam.vector import Polyline


def test_polyline_requires_at_least_two_points() -> None:
    with pytest.raises(ValueError):
        Polyline(points=((0.0, 0.0),))


def test_length_of_open_polyline() -> None:
    line = Polyline(points=((0.0, 0.0), (3.0, 4.0)))
    assert line.length_mm() == pytest.approx(5.0)


def test_length_of_open_chain() -> None:
    line = Polyline(points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)))
    assert line.length_mm() == pytest.approx(2.0)


def test_length_of_closed_polyline_includes_closing_segment() -> None:
    square = Polyline(
        points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        closed=True,
    )
    assert square.length_mm() == pytest.approx(4.0)


def test_bbox_returns_min_max_xy() -> None:
    poly = Polyline(points=((1.0, 2.0), (3.0, -1.0), (-2.0, 4.0)))
    assert poly.bbox() == (-2.0, -1.0, 3.0, 4.0)


def test_closed_polyline_is_marked() -> None:
    poly = Polyline(points=((0.0, 0.0), (1.0, 0.0)), closed=True)
    assert poly.closed is True
    assert poly.length_mm() == pytest.approx(2.0)


def test_polyline_with_diagonal_segment() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 4.0), (6.0, 0.0)))
    assert poly.length_mm() == pytest.approx(10.0)
    assert math.isfinite(poly.length_mm())
