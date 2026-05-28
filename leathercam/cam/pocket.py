"""Pocket (area clearing) toolpath strategy.

For each closed input polyline, computes a cascade of inward offsets:
- ring 0 sits at -tool_radius (just inside the boundary),
- ring k sits at -(tool_radius + k * step_over),
until the resulting set is empty.

Each ring is traced at every Z pass. Open polylines are skipped — pocketing
needs a closed boundary to define the cleared area.
"""

from __future__ import annotations

import math

import pyclipper

from leathercam.cam.profile import _trace_polyline
from leathercam.gcode import Move
from leathercam.vector import Polyline

_CLIPPER_SCALE = 1000.0


def pocket(
    polylines: list[Polyline],
    *,
    depth_mm: float,
    step_down_mm: float,
    safe_z: float,
    tool_diameter_mm: float,
    step_over_mm: float,
    origin: tuple[float, float] = (0.0, 0.0),
) -> list[Move]:
    if depth_mm <= 0:
        raise ValueError("depth_mm must be positive")
    if step_down_mm <= 0:
        raise ValueError("step_down_mm must be positive")
    if safe_z <= 0:
        raise ValueError("safe_z must be positive")
    if tool_diameter_mm <= 0:
        raise ValueError("tool_diameter_mm must be positive")
    if step_over_mm <= 0:
        raise ValueError("step_over_mm must be positive")
    if step_over_mm > tool_diameter_mm:
        raise ValueError("step_over_mm must not exceed tool diameter")

    radius = tool_diameter_mm / 2.0
    n_passes = math.ceil(depth_mm / step_down_mm)
    z_levels = [-min(step_down_mm * i, depth_mm) for i in range(1, n_passes + 1)]
    ox, oy = origin

    rings_per_polygon: list[list[Polyline]] = []
    for poly in polylines:
        if not poly.closed:
            continue
        rings = _cascade_offsets(poly, radius, step_over_mm)
        shifted = [
            Polyline(points=tuple((x + ox, y + oy) for x, y in r.points), closed=True)
            for r in rings
        ]
        if shifted:
            rings_per_polygon.append(shifted)

    moves: list[Move] = []
    for z in z_levels:
        for rings in rings_per_polygon:
            for ring in rings:
                moves.extend(_trace_polyline(ring, z, safe_z))
    return moves


def _cascade_offsets(poly: Polyline, radius_mm: float, step_over_mm: float) -> list[Polyline]:
    scaled = [(round(x * _CLIPPER_SCALE), round(y * _CLIPPER_SCALE)) for x, y in poly.points]
    if len(scaled) >= 2 and scaled[-1] == scaled[0]:
        scaled = scaled[:-1]

    pco = pyclipper.PyclipperOffset()
    pco.AddPath(scaled, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)

    rings: list[Polyline] = []
    level = radius_mm
    while True:
        result = pco.Execute(-level * _CLIPPER_SCALE)
        if not result:
            break
        for path in result:
            pts = tuple((x / _CLIPPER_SCALE, y / _CLIPPER_SCALE) for x, y in path)
            if len(pts) >= 2:
                rings.append(Polyline(points=pts, closed=True))
        level += step_over_mm
    return rings
