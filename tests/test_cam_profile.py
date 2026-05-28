"""Tests for the Profile (contour) toolpath strategy."""

from __future__ import annotations

import pytest

from leathercam.cam import profile
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


def test_on_side_traces_polyline_exactly_for_closed_shape() -> None:
    poly = _square()
    moves = profile(
        [poly], depth_mm=0.5, step_down_mm=0.5, safe_z=5.0, tool_diameter_mm=1.0, side="on"
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox == (0.0, 0.0, 10.0, 10.0)


def test_inside_offset_shrinks_closed_polygon() -> None:
    moves = profile(
        [_square()],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="inside",
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox[0] == pytest.approx(0.5, abs=0.05)
    assert bbox[1] == pytest.approx(0.5, abs=0.05)
    assert bbox[2] == pytest.approx(9.5, abs=0.05)
    assert bbox[3] == pytest.approx(9.5, abs=0.05)


def test_outside_offset_expands_closed_polygon() -> None:
    moves = profile(
        [_square()],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="outside",
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox[0] == pytest.approx(-0.5, abs=0.05)
    assert bbox[1] == pytest.approx(-0.5, abs=0.05)
    assert bbox[2] == pytest.approx(10.5, abs=0.05)
    assert bbox[3] == pytest.approx(10.5, abs=0.05)


def test_open_polyline_ignores_side_setting() -> None:
    poly = _open_chain()
    moves_on = profile(
        [poly], depth_mm=0.5, step_down_mm=0.5, safe_z=5.0, tool_diameter_mm=1.0, side="on"
    )
    moves_inside = profile(
        [poly], depth_mm=0.5, step_down_mm=0.5, safe_z=5.0, tool_diameter_mm=1.0, side="inside"
    )
    assert _bbox_of_cuts(moves_on) == _bbox_of_cuts(moves_inside)


def test_closed_polyline_returns_to_start_at_each_pass() -> None:
    moves = profile(
        [_square()],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="on",
    )
    cuts = [m for m in moves if not m.rapid]
    assert cuts[0].x == pytest.approx(cuts[-1].x)
    assert cuts[0].y == pytest.approx(cuts[-1].y)


def test_open_polyline_does_not_return_to_start() -> None:
    moves = profile(
        [_open_chain()],
        depth_mm=0.4,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="on",
    )
    cuts = [m for m in moves if not m.rapid]
    assert (cuts[0].x, cuts[0].y) == (0.0, 0.0)
    assert (cuts[-1].x, cuts[-1].y) == (10.0, 10.0)


def test_step_down_creates_multiple_passes() -> None:
    moves = profile(
        [_square()],
        depth_mm=1.0,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="on",
    )
    cut_depths = sorted({m.z for m in moves if not m.rapid})
    assert cut_depths == [-1.0, -0.8, -0.4]


def test_origin_shifts_all_coordinates() -> None:
    moves = profile(
        [_square()],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="on",
        origin=(50.0, 100.0),
    )
    bbox = _bbox_of_cuts(moves)
    assert bbox == (50.0, 100.0, 60.0, 110.0)


def test_rapid_to_safe_z_between_passes() -> None:
    moves = profile(
        [_square()],
        depth_mm=0.8,
        step_down_mm=0.4,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="on",
    )
    safe_retracts = [m for m in moves if m.rapid and m.z == 5.0]
    assert len(safe_retracts) >= 4


def test_multiple_polylines_each_get_their_own_traverse() -> None:
    a = _square()
    b = Polyline(
        points=((20.0, 20.0), (30.0, 20.0), (30.0, 30.0), (20.0, 30.0)),
        closed=True,
    )
    moves = profile(
        [a, b], depth_mm=0.4, step_down_mm=0.4, safe_z=5.0, tool_diameter_mm=1.0, side="on"
    )
    safe_rapids = [(m.x, m.y) for m in moves if m.rapid and m.z == 5.0]
    assert (0.0, 0.0) in safe_rapids
    assert (20.0, 20.0) in safe_rapids


def test_inside_offset_can_eliminate_small_polygon() -> None:
    tiny = Polyline(
        points=((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)),
        closed=True,
    )
    moves = profile(
        [tiny],
        depth_mm=0.5,
        step_down_mm=0.5,
        safe_z=5.0,
        tool_diameter_mm=1.0,
        side="inside",
    )
    assert moves == []


def test_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        profile([_square()], depth_mm=0.0, step_down_mm=0.4, safe_z=5.0, tool_diameter_mm=1.0)
    with pytest.raises(ValueError):
        profile([_square()], depth_mm=0.4, step_down_mm=0.0, safe_z=5.0, tool_diameter_mm=1.0)
    with pytest.raises(ValueError):
        profile([_square()], depth_mm=0.4, step_down_mm=0.4, safe_z=-1.0, tool_diameter_mm=1.0)
    with pytest.raises(ValueError):
        profile([_square()], depth_mm=0.4, step_down_mm=0.4, safe_z=5.0, tool_diameter_mm=0.0)
    with pytest.raises(ValueError):
        profile(
            [_square()],
            depth_mm=0.4,
            step_down_mm=0.4,
            safe_z=5.0,
            tool_diameter_mm=1.0,
            side="wrong",  # type: ignore[arg-type]
        )
