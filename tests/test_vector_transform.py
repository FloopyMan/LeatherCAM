"""Tests for vector transforms."""

from __future__ import annotations

import pytest

from leathercam.vector import Polyline, mirror_x


def test_mirror_empty_input() -> None:
    assert mirror_x([]) == []


def test_mirror_horizontal_line_keeps_bbox() -> None:
    poly = Polyline(points=((0.0, 5.0), (10.0, 5.0)))
    flipped = mirror_x([poly])[0]
    xs = [p[0] for p in flipped.points]
    assert min(xs) == pytest.approx(0.0)
    assert max(xs) == pytest.approx(10.0)


def test_mirror_reverses_x_order() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 0.0), (10.0, 5.0)))
    flipped = mirror_x([poly])[0]
    assert flipped.points[0][0] == pytest.approx(10.0)
    assert flipped.points[1][0] == pytest.approx(7.0)
    assert flipped.points[2][0] == pytest.approx(0.0)


def test_mirror_preserves_y_coordinates() -> None:
    poly = Polyline(points=((0.0, 2.0), (10.0, 8.0)))
    flipped = mirror_x([poly])[0]
    assert flipped.points[0][1] == pytest.approx(2.0)
    assert flipped.points[1][1] == pytest.approx(8.0)


def test_mirror_preserves_closed_flag() -> None:
    poly = Polyline(points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)), closed=True)
    flipped = mirror_x([poly])[0]
    assert flipped.closed is True


def test_mirror_is_involution() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 4.0), (10.0, 2.0)))
    twice = mirror_x(mirror_x([poly]))[0]
    for original, restored in zip(poly.points, twice.points, strict=True):
        assert original[0] == pytest.approx(restored[0])
        assert original[1] == pytest.approx(restored[1])


def test_mirror_uses_combined_bbox_across_multiple_polylines() -> None:
    a = Polyline(points=((0.0, 0.0), (4.0, 0.0)))
    b = Polyline(points=((10.0, 0.0), (20.0, 0.0)))
    [fa, fb] = mirror_x([a, b])
    fa_xs = sorted(p[0] for p in fa.points)
    fb_xs = sorted(p[0] for p in fb.points)
    assert fa_xs == [pytest.approx(16.0), pytest.approx(20.0)]
    assert fb_xs == [pytest.approx(0.0), pytest.approx(10.0)]
