"""Tests for outer/hole grouping of closed polylines."""

from __future__ import annotations

import pytest

from leathercam.vector import Polyline, group_with_holes
from leathercam.vector.grouping import ensure_ccw, ensure_cw, signed_area


def _ring(cx: float, cy: float, r: float, n: int = 32) -> Polyline:
    import math

    pts = tuple(
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    )
    return Polyline(points=pts, closed=True)


def test_signed_area_positive_for_ccw_square() -> None:
    pts = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    assert signed_area(pts) > 0


def test_signed_area_negative_for_cw_square() -> None:
    pts = ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0))
    assert signed_area(pts) < 0


def test_ensure_ccw_reverses_cw() -> None:
    pts = ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0))
    flipped = ensure_ccw(pts)
    assert signed_area(flipped) > 0


def test_ensure_cw_reverses_ccw() -> None:
    pts = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    flipped = ensure_cw(pts)
    assert signed_area(flipped) < 0


def test_empty_input() -> None:
    assert group_with_holes([]) == []


def test_open_polylines_are_ignored() -> None:
    chain = Polyline(points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=False)
    assert group_with_holes([chain]) == []


def test_single_closed_polygon_has_no_holes() -> None:
    sq = Polyline(
        points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        closed=True,
    )
    groups = group_with_holes([sq])
    assert len(groups) == 1
    assert groups[0].outer is sq
    assert groups[0].holes == ()


def test_letter_o_outer_with_one_hole() -> None:
    outer = _ring(0.0, 0.0, 10.0)
    inner = _ring(0.0, 0.0, 5.0)
    groups = group_with_holes([outer, inner])
    assert len(groups) == 1
    assert groups[0].outer is outer
    assert len(groups[0].holes) == 1
    assert groups[0].holes[0] is inner


def test_two_disjoint_letters_each_keep_their_hole() -> None:
    o1_outer = _ring(0.0, 0.0, 5.0)
    o1_inner = _ring(0.0, 0.0, 2.0)
    o2_outer = _ring(20.0, 0.0, 5.0)
    o2_inner = _ring(20.0, 0.0, 2.0)
    groups = group_with_holes([o1_outer, o1_inner, o2_outer, o2_inner])
    assert len(groups) == 2
    by_center_x = sorted(groups, key=lambda g: g.outer.points[0][0])
    assert all(len(g.holes) == 1 for g in by_center_x)


def test_island_inside_hole_becomes_its_own_outer() -> None:
    outer = _ring(0.0, 0.0, 10.0)
    hole = _ring(0.0, 0.0, 6.0)
    island = _ring(0.0, 0.0, 2.0)
    groups = group_with_holes([outer, hole, island])
    assert len(groups) == 2
    outer_group = next(g for g in groups if g.outer is outer)
    island_group = next(g for g in groups if g.outer is island)
    assert hole in outer_group.holes
    assert island_group.holes == ()


def test_order_independent() -> None:
    outer = _ring(0.0, 0.0, 10.0)
    inner = _ring(0.0, 0.0, 5.0)
    a = group_with_holes([outer, inner])
    b = group_with_holes([inner, outer])
    assert len(a) == len(b) == 1
    assert a[0].outer is outer and b[0].outer is outer


def test_degenerate_polygon_is_skipped() -> None:
    bad = Polyline(points=((0.0, 0.0), (1.0, 0.0)), closed=True)
    with pytest.raises(ValueError):
        Polyline(points=((0.0, 0.0),), closed=True)
    assert group_with_holes([bad]) == []
