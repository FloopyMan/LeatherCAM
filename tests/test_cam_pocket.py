"""Tests for the pocket (area clearing) strategy."""

from __future__ import annotations

import pytest

from leathercam.cam import pocket
from leathercam.vector import Polyline


def _square(size: float = 10.0) -> Polyline:
    return Polyline(
        points=((0.0, 0.0), (size, 0.0), (size, size), (0.0, size)),
        closed=True,
    )


def _open_chain() -> Polyline:
    return Polyline(points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=False)


def _bbox_of_cuts(moves) -> tuple[float, float, float, float]:
    cuts = [(m.x, m.y) for m in moves if not m.rapid]
    xs = [x for x, _ in cuts]
    ys = [y for _, y in cuts]
    return (min(xs), min(ys), max(xs), max(ys))


def test_pocket_yields_rings_inside_polygon() -> None:
    moves = pocket(
        [_square(10.0)],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox[0] >= 0.5 - 0.05
    assert bbox[2] <= 9.5 + 0.05


def test_open_polylines_are_skipped() -> None:
    moves = pocket(
        [_open_chain()],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    assert moves == []


def test_smaller_step_over_produces_more_rings() -> None:
    coarse = pocket(
        [_square(10.0)],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.8,
    )
    fine = pocket(
        [_square(10.0)],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.2,
    )
    coarse_safe = sum(1 for m in coarse if m.rapid and m.z == 5.0)
    fine_safe = sum(1 for m in fine if m.rapid and m.z == 5.0)
    assert fine_safe > coarse_safe * 2


def test_step_down_creates_multiple_passes() -> None:
    moves = pocket(
        [_square(10.0)],
        depth_mm=1.0,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    cut_depths = sorted({m.z for m in moves if not m.rapid})
    assert cut_depths == [-1.0, -0.8, -0.4]


def test_origin_shifts_all_coordinates() -> None:
    moves = pocket(
        [_square(10.0)],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
        origin=(100.0, 200.0),
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox[0] >= 100.0
    assert bbox[1] >= 200.0
    assert bbox[2] <= 110.0
    assert bbox[3] <= 210.0


def test_polygon_smaller_than_tool_produces_no_moves() -> None:
    tiny = Polyline(
        points=((0.0, 0.0), (0.4, 0.0), (0.4, 0.4), (0.0, 0.4)),
        closed=True,
    )
    moves = pocket(
        [tiny],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    assert moves == []


def test_multiple_polygons_are_each_pocketed() -> None:
    a = _square(10.0)
    b = Polyline(
        points=((20.0, 20.0), (30.0, 20.0), (30.0, 30.0), (20.0, 30.0)),
        closed=True,
    )
    moves = pocket(
        [a, b],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    cuts = [(m.x, m.y) for m in moves if not m.rapid]
    assert any(x < 10 and y < 10 for x, y in cuts)
    assert any(20 < x < 30 and 20 < y < 30 for x, y in cuts)


def test_pocket_visits_first_ring_close_to_boundary() -> None:
    moves = pocket(
        [_square(10.0)],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox[0] == pytest.approx(0.5, abs=0.05)
    assert bbox[2] == pytest.approx(9.5, abs=0.05)


def test_rejects_invalid_parameters() -> None:
    sq = _square()
    for bad in (
        {"depth_mm": 0.0},
        {"step_down_mm": 0.0},
        {"safe_z": -1.0},
        {"tool_diameter_mm": 0.0},
        {"step_over_mm": 0.0},
        {"step_over_mm": 2.0, "tool_diameter_mm": 1.0},
    ):
        kwargs: dict[str, object] = {
            "depth_mm": 0.4,
            "step_down_mm": 0.4,
            "safe_z": 5.0,
            "tool_diameter_mm": 1.0,
            "step_over_mm": 0.5,
            **bad,
        }
        with pytest.raises(ValueError):
            pocket([sq], **kwargs)  # type: ignore[arg-type]
