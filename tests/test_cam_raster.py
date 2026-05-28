"""Tests for the raster zigzag strategy."""

from __future__ import annotations

import numpy as np
import pytest

from leathercam.cam import raster_zigzag
from leathercam.cam.raster import _find_runs
from leathercam.image.preprocess import Raster


def _mask(rows: list[str]) -> Raster:
    arr = np.array([[ch == "#" for ch in row] for row in rows], dtype=np.bool_)
    return Raster(mask=arr, pixel_size_mm=1.0)


def test_find_runs_empty_row() -> None:
    assert _find_runs(np.zeros(5, dtype=np.bool_)) == []


def test_find_runs_single_run_full_row() -> None:
    assert _find_runs(np.ones(5, dtype=np.bool_)) == [(0, 4)]


def test_find_runs_multiple_disjoint_runs() -> None:
    row = np.array([1, 1, 0, 0, 1, 0, 1, 1, 1], dtype=np.bool_)
    assert _find_runs(row) == [(0, 1), (4, 4), (6, 8)]


def test_find_runs_run_at_end_of_row() -> None:
    row = np.array([0, 0, 1, 1], dtype=np.bool_)
    assert _find_runs(row) == [(2, 3)]


def test_empty_mask_produces_no_moves() -> None:
    raster = _mask(["...", "...", "..."])
    moves = raster_zigzag(raster, depth_mm=0.5, step_down_mm=0.5, safe_z=5.0)
    assert moves == []


def test_single_pixel_produces_plunge_traverse_retract() -> None:
    raster = _mask(["#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0)
    assert len(moves) == 4
    rapid_in, plunge, traverse, retract = moves
    assert rapid_in.rapid and rapid_in.z == 5.0
    assert plunge.z == pytest.approx(-0.4) and not plunge.rapid
    assert traverse.z == pytest.approx(-0.4) and not traverse.rapid
    assert retract.rapid and retract.z == 5.0


def test_pixel_centers_are_used_for_xy() -> None:
    raster = _mask(["#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0)
    assert moves[0].x == pytest.approx(0.5)
    assert moves[0].y == pytest.approx(0.5)


def test_origin_offset_shifts_all_xy() -> None:
    raster = _mask(["#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0, origin=(10.0, 20.0))
    assert moves[0].x == pytest.approx(10.5)
    assert moves[0].y == pytest.approx(20.5)


def test_y_inversion_top_row_has_highest_y() -> None:
    raster = _mask(["#", ".", "#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0)
    top_cut = moves[0]
    bottom_cut = moves[4]
    assert top_cut.y == pytest.approx(2.5)
    assert bottom_cut.y == pytest.approx(0.5)


def test_zigzag_reverses_direction_on_odd_rows() -> None:
    raster = _mask(["####", "####"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0)
    row0_plunge_x = moves[1].x
    row0_traverse_end_x = moves[2].x
    row1_plunge_x = moves[5].x
    row1_traverse_end_x = moves[6].x
    assert row0_plunge_x < row0_traverse_end_x
    assert row1_plunge_x > row1_traverse_end_x
    assert row1_plunge_x == pytest.approx(row0_traverse_end_x)


def test_step_down_creates_multiple_passes() -> None:
    raster = _mask(["#"])
    moves = raster_zigzag(raster, depth_mm=1.0, step_down_mm=0.4, safe_z=5.0)
    assert len(moves) == 12
    plunge_depths = sorted({m.z for m in moves if not m.rapid})
    assert plunge_depths == [-1.0, -0.8, -0.4]


def test_step_down_larger_than_depth_yields_single_pass() -> None:
    raster = _mask(["#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=1.0, safe_z=5.0)
    cut_depths = {m.z for m in moves if not m.rapid}
    assert cut_depths == {-0.4}


def test_disjoint_runs_in_row_each_get_their_own_plunge() -> None:
    raster = _mask(["#.#"])
    moves = raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=5.0)
    assert len(moves) == 8
    assert moves[0].x == pytest.approx(0.5)
    assert moves[4].x == pytest.approx(2.5)


def test_rejects_invalid_parameters() -> None:
    raster = _mask(["#"])
    with pytest.raises(ValueError):
        raster_zigzag(raster, depth_mm=0.0, step_down_mm=0.4, safe_z=5.0)
    with pytest.raises(ValueError):
        raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.0, safe_z=5.0)
    with pytest.raises(ValueError):
        raster_zigzag(raster, depth_mm=0.4, step_down_mm=0.4, safe_z=-1.0)
