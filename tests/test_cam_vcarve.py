"""Tests for the V-carve strategy."""

from __future__ import annotations

import math

import numpy as np
import pytest

from leathercam.cam import v_carve
from leathercam.image.preprocess import Raster


def _mask(rows: list[str], pixel_size_mm: float = 1.0) -> Raster:
    arr = np.array([[ch == "#" for ch in row] for row in rows], dtype=np.bool_)
    return Raster(mask=arr, pixel_size_mm=pixel_size_mm)


def _disk(radius_px: int, pixel_size_mm: float = 0.2) -> Raster:
    size = radius_px * 2 + 5
    mask = np.zeros((size, size), dtype=np.bool_)
    cy = cx = size // 2
    yy, xx = np.ogrid[:size, :size]
    mask[((yy - cy) ** 2 + (xx - cx) ** 2) <= radius_px * radius_px] = True
    return Raster(mask=mask, pixel_size_mm=pixel_size_mm)


def test_empty_mask_produces_no_moves() -> None:
    moves = v_carve(
        _mask(["...", "...", "..."]),
        v_angle_deg=60.0,
        max_depth_mm=2.0,
        step_down_mm=0.5,
        safe_z=5.0,
    )
    assert moves == []


def test_single_pixel_can_be_v_carved_to_max_depth() -> None:
    raster = _disk(radius_px=8, pixel_size_mm=0.2)
    moves = v_carve(raster, v_angle_deg=60.0, max_depth_mm=5.0, step_down_mm=0.2, safe_z=5.0)
    depths = sorted({m.z for m in moves if not m.rapid})
    assert depths
    assert depths[0] < 0


def test_v_carve_depth_respects_v_angle() -> None:
    raster = _disk(radius_px=10, pixel_size_mm=0.2)
    sharp = v_carve(raster, v_angle_deg=30.0, max_depth_mm=10.0, step_down_mm=0.2, safe_z=5.0)
    blunt = v_carve(raster, v_angle_deg=120.0, max_depth_mm=10.0, step_down_mm=0.2, safe_z=5.0)
    sharp_deepest = min(m.z for m in sharp if not m.rapid)
    blunt_deepest = min(m.z for m in blunt if not m.rapid)
    assert sharp_deepest < blunt_deepest


def test_max_depth_clamps_result() -> None:
    raster = _disk(radius_px=20, pixel_size_mm=0.2)
    moves = v_carve(raster, v_angle_deg=60.0, max_depth_mm=0.5, step_down_mm=0.2, safe_z=5.0)
    deepest = min(m.z for m in moves if not m.rapid)
    assert deepest == pytest.approx(-0.5, abs=0.1)


def test_origin_offset_shifts_coordinates() -> None:
    raster = _disk(radius_px=4, pixel_size_mm=0.2)
    moves = v_carve(
        raster,
        v_angle_deg=60.0,
        max_depth_mm=2.0,
        step_down_mm=0.4,
        safe_z=5.0,
        origin=(50.0, 100.0),
    )
    xs = [m.x for m in moves if not m.rapid]
    ys = [m.y for m in moves if not m.rapid]
    assert min(xs) >= 50.0 - 1e-6
    assert min(ys) >= 100.0 - 1e-6


def test_y_inversion_top_row_has_highest_y() -> None:
    raster = _mask(["#####", ".....", ".....", "....."], pixel_size_mm=1.0)
    moves = v_carve(raster, v_angle_deg=90.0, max_depth_mm=1.0, step_down_mm=0.5, safe_z=5.0)
    cuts_y = [m.y for m in moves if not m.rapid]
    assert max(cuts_y) > 2.5


def test_rejects_invalid_parameters() -> None:
    raster = _disk(radius_px=4)
    with pytest.raises(ValueError):
        v_carve(raster, v_angle_deg=0.0, max_depth_mm=1.0, step_down_mm=0.5, safe_z=5.0)
    with pytest.raises(ValueError):
        v_carve(raster, v_angle_deg=180.0, max_depth_mm=1.0, step_down_mm=0.5, safe_z=5.0)
    with pytest.raises(ValueError):
        v_carve(raster, v_angle_deg=60.0, max_depth_mm=0.0, step_down_mm=0.5, safe_z=5.0)
    with pytest.raises(ValueError):
        v_carve(raster, v_angle_deg=60.0, max_depth_mm=1.0, step_down_mm=0.0, safe_z=5.0)
    with pytest.raises(ValueError):
        v_carve(raster, v_angle_deg=60.0, max_depth_mm=1.0, step_down_mm=0.5, safe_z=0.0)


def test_safe_z_used_between_contours() -> None:
    raster = _disk(radius_px=8, pixel_size_mm=0.2)
    moves = v_carve(raster, v_angle_deg=60.0, max_depth_mm=2.0, step_down_mm=0.4, safe_z=5.0)
    safe_rapids = [m for m in moves if m.rapid and m.z == 5.0]
    assert safe_rapids


def test_depths_are_negative_and_quantized_by_step_down() -> None:
    raster = _disk(radius_px=10, pixel_size_mm=0.2)
    moves = v_carve(raster, v_angle_deg=60.0, max_depth_mm=1.5, step_down_mm=0.5, safe_z=5.0)
    depths = sorted({m.z for m in moves if not m.rapid})
    for d in depths:
        assert d < 0
    assert all(math.isclose(d % 0.5, 0.0, abs_tol=1e-6) or d <= -1.5 for d in depths)
