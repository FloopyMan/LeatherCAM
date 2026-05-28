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


def test_letter_o_keeps_inner_hole_uncut() -> None:
    """For an annulus (outer ring + inner hole) the pocket must leave the
    central area uncut. Concretely: no cut moves should land inside the
    hole."""
    import math

    def ring(cx: float, cy: float, r: float, n: int = 64) -> Polyline:
        pts = tuple(
            (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        )
        return Polyline(points=pts, closed=True)

    outer = ring(10.0, 10.0, 8.0)
    inner = ring(10.0, 10.0, 3.0)
    moves = pocket(
        [outer, inner],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    cuts = [(m.x, m.y) for m in moves if not m.rapid]
    assert cuts, "expected non-empty toolpath for the ring"
    keep_out_radius = 3.0 + 0.5 - 0.05  # hole + tool radius - tolerance
    for x, y in cuts:
        d = math.hypot(x - 10.0, y - 10.0)
        assert d >= keep_out_radius, (
            f"cut at ({x:.3f}, {y:.3f}) is {d:.3f}mm from center — "
            f"closer than the hole radius {keep_out_radius:.3f}"
        )


def test_two_letters_each_keep_their_holes() -> None:
    import math

    def ring(cx: float, cy: float, r: float, n: int = 48) -> Polyline:
        pts = tuple(
            (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        )
        return Polyline(points=pts, closed=True)

    o1_outer, o1_inner = ring(0.0, 0.0, 6.0), ring(0.0, 0.0, 2.5)
    o2_outer, o2_inner = ring(20.0, 0.0, 6.0), ring(20.0, 0.0, 2.5)
    moves = pocket(
        [o1_outer, o1_inner, o2_outer, o2_inner],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        step_over_mm=0.5,
    )
    cuts = [(m.x, m.y) for m in moves if not m.rapid]
    for x, y in cuts:
        d1 = math.hypot(x, y)
        d2 = math.hypot(x - 20.0, y)
        assert d1 >= 2.9 or d2 >= 2.9, f"cut at ({x:.2f}, {y:.2f}) sits inside one of the holes"


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
