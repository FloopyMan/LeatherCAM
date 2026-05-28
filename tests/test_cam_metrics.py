"""Tests for toolpath metrics: bounding box, time estimate, bounds check."""

from __future__ import annotations

import math

import pytest

from leathercam.cam import (
    CNC_3018_BOUNDS_MM,
    BoundingBox,
    bounding_box,
    estimate_duration_minutes,
    exceeds_bounds,
)
from leathercam.gcode import Move


def test_bounding_box_of_empty_moves_is_none() -> None:
    assert bounding_box([]) is None


def test_bounding_box_of_single_move_collapses() -> None:
    box = bounding_box([Move(x=5.0, y=6.0, z=-0.4, rapid=False)])
    assert box == BoundingBox(5.0, 6.0, -0.4, 5.0, 6.0, -0.4)


def test_bounding_box_min_max_across_moves() -> None:
    moves = [
        Move(x=1.0, y=2.0, z=5.0, rapid=True),
        Move(x=10.0, y=2.0, z=-0.5, rapid=False),
        Move(x=-3.0, y=8.0, z=0.0, rapid=False),
    ]
    box = bounding_box(moves)
    assert box == BoundingBox(-3.0, 2.0, -0.5, 10.0, 8.0, 5.0)
    assert box.width == pytest.approx(13.0)
    assert box.depth == pytest.approx(6.0)
    assert box.height == pytest.approx(5.5)


def test_estimate_duration_empty_returns_zero() -> None:
    assert estimate_duration_minutes([], feed_xy=600, feed_z=200) == 0.0


def test_estimate_duration_single_move_returns_zero() -> None:
    assert (
        estimate_duration_minutes([Move(x=0.0, y=0.0, z=0.0, rapid=False)], feed_xy=600, feed_z=200)
        == 0.0
    )


def test_estimate_duration_uses_feed_xy_for_horizontal() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=-0.4, rapid=False),
        Move(x=600.0, y=0.0, z=-0.4, rapid=False),
    ]
    minutes = estimate_duration_minutes(moves, feed_xy=600, feed_z=200)
    assert minutes == pytest.approx(1.0)


def test_estimate_duration_uses_feed_z_for_pure_plunge() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
        Move(x=0.0, y=0.0, z=-200.0 / 6.0, rapid=False),
    ]
    minutes = estimate_duration_minutes(moves, feed_xy=600, feed_z=200)
    assert minutes == pytest.approx(1.0 / 6.0, abs=1e-6)


def test_estimate_duration_uses_rapid_feed_for_g0() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=5.0, rapid=True),
        Move(x=200.0, y=0.0, z=5.0, rapid=True),
    ]
    minutes = estimate_duration_minutes(moves, feed_xy=600, feed_z=200, rapid_feed=2000.0)
    assert minutes == pytest.approx(0.1)


def test_estimate_duration_skips_zero_length_segments() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
        Move(x=600.0, y=0.0, z=0.0, rapid=False),
    ]
    assert estimate_duration_minutes(moves, feed_xy=600, feed_z=200) == pytest.approx(1.0)


def test_exceeds_bounds_no_bbox_returns_empty() -> None:
    assert exceeds_bounds(None) == []


def test_exceeds_bounds_inside_machine_has_no_warnings() -> None:
    box = BoundingBox(0.0, 0.0, -2.0, 100.0, 80.0, 5.0)
    assert exceeds_bounds(box, safe_z=5.0) == []


def test_exceeds_bounds_warns_each_axis() -> None:
    box = BoundingBox(-1.0, 0.0, -50.0, 350.0, 200.0, 10.0)
    warnings = exceeds_bounds(box, machine=CNC_3018_BOUNDS_MM, safe_z=5.0)
    text = " | ".join(warnings)
    assert "X выходит за 0" in text
    assert "X выходит за 300" in text
    assert "Y выходит за 180" in text
    assert "Z уходит глубже" in text
    assert "Z поднимается выше" in text


def test_exceeds_bounds_negative_z_allowed_within_travel() -> None:
    box = BoundingBox(0.0, 0.0, -40.0, 100.0, 100.0, 5.0)
    assert exceeds_bounds(box, safe_z=5.0) == []


def test_estimate_combined_motion_uses_xy_feed() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
        Move(x=300.0, y=400.0, z=-1.0, rapid=False),
    ]
    minutes = estimate_duration_minutes(moves, feed_xy=500, feed_z=100)
    expected = math.hypot(300.0, 400.0 + 0.0) / 500.0
    expected = math.sqrt(300**2 + 400**2 + 1**2) / 500.0
    assert minutes == pytest.approx(expected, abs=1e-6)
