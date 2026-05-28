"""Raster zigzag toolpath strategy.

For each Z level (step-down passes), walks the mask row by row, alternating
left-to-right / right-to-left for adjacent rows (zigzag). Within a row, each
contiguous run of True pixels becomes a plunge → traverse → retract sequence.

Coordinate convention:
- Image row 0 maps to the highest machine Y (image is upright on the bed).
- Pixel centers are used for X/Y, so the engraved trace is centered on each
  pixel of width pixel_size_mm.
"""

from __future__ import annotations

import math

import numpy as np

from leathercam.gcode import Move
from leathercam.image.preprocess import Raster


def raster_zigzag(
    raster: Raster,
    depth_mm: float,
    step_down_mm: float,
    safe_z: float,
    origin: tuple[float, float] = (0.0, 0.0),
) -> list[Move]:
    """Generate a list of Moves that engrave every True pixel of the mask.

    depth_mm     — total cut depth (positive number, becomes negative Z).
    step_down_mm — maximum depth removed per pass.
    safe_z       — Z above the workpiece for rapid travel.
    origin       — machine (X, Y) of the bottom-left corner of the raster.
    """
    if depth_mm <= 0:
        raise ValueError("depth_mm must be positive")
    if step_down_mm <= 0:
        raise ValueError("step_down_mm must be positive")
    if safe_z <= 0:
        raise ValueError("safe_z must be positive (above the workpiece)")

    mask = raster.mask
    height_px, _ = mask.shape
    px = raster.pixel_size_mm
    ox, oy = origin

    n_passes = math.ceil(depth_mm / step_down_mm)
    z_levels = [-min(step_down_mm * i, depth_mm) for i in range(1, n_passes + 1)]

    def x_of_col(c: int) -> float:
        return ox + (c + 0.5) * px

    def y_of_row(r: int) -> float:
        return oy + (height_px - 1 - r + 0.5) * px

    moves: list[Move] = []
    for z in z_levels:
        for r in range(height_px):
            runs = _find_runs(mask[r])
            if not runs:
                continue
            if r % 2 == 1:
                runs = [(end, start) for (start, end) in reversed(runs)]
            y = y_of_row(r)
            for c_start, c_end in runs:
                x_start = x_of_col(c_start)
                x_end = x_of_col(c_end)
                moves.append(Move(x=x_start, y=y, z=safe_z, rapid=True))
                moves.append(Move(x=x_start, y=y, z=z, rapid=False))
                moves.append(Move(x=x_end, y=y, z=z, rapid=False))
                moves.append(Move(x=x_end, y=y, z=safe_z, rapid=True))
    return moves


def _find_runs(row: np.ndarray) -> list[tuple[int, int]]:
    """Return (start_col, end_col) inclusive pairs for contiguous True runs."""
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for c in range(int(row.shape[0])):
        if row[c]:
            if not in_run:
                start = c
                in_run = True
        elif in_run:
            runs.append((start, c - 1))
            in_run = False
    if in_run:
        runs.append((start, int(row.shape[0]) - 1))
    return runs
