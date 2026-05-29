"""Pocket (area clearing) toolpath strategy.

For each closed input polyline (or polygon-with-holes), computes a cascade
of inward offsets:
- ring 0 sits at -tool_radius (just inside the boundary),
- ring k sits at -(tool_radius + k * step_over),
until the resulting set is empty.

Each ring is traced at every Z pass. Open polylines are skipped — pocketing
needs a closed boundary to define the cleared area. Polylines that sit
inside another polyline (e.g. the inner ring of an "O" glyph) are treated
as holes: pyclipper inflates them outward by tool_radius, so the area
inside the hole stays uncut.
"""

from __future__ import annotations

import math
from typing import Literal

import pyclipper

from leathercam.cam.profile import _trace_polyline
from leathercam.gcode import Move
from leathercam.vector import PolygonWithHoles, Polyline, group_with_holes
from leathercam.vector.grouping import ensure_ccw, ensure_cw

_CLIPPER_SCALE = 1000.0
# pyclipper ArcTolerance is in scaled-int units. Default 0.25 ≙ 0.00025mm
# at our scale, which produces ~30+ micro-segments per 90° corner — the
# GRBL planner stutters on those. 50 ≙ 0.05mm — visually identical at
# typical cliché sizes but ~5× fewer segments per arc.
_CLIPPER_ARC_TOL = 50.0

PocketMode = Literal["design", "background"]


def pocket(
    polylines: list[Polyline],
    *,
    depth_mm: float,
    step_down_mm: float,
    safe_z: float,
    tool_diameter_mm: float,
    step_over_mm: float,
    origin: tuple[float, float] = (0.0, 0.0),
    mode: PocketMode = "design",
    workpiece_size_mm: tuple[float, float] | None = None,
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
    if mode not in ("design", "background"):
        raise ValueError(f"invalid pocket mode: {mode!r}")
    if mode == "background" and workpiece_size_mm is None:
        raise ValueError("background mode requires workpiece_size_mm")

    radius = tool_diameter_mm / 2.0
    n_passes = math.ceil(depth_mm / step_down_mm)
    z_levels = [-min(step_down_mm * i, depth_mm) for i in range(1, n_passes + 1)]
    ox, oy = origin

    if mode == "background":
        assert workpiece_size_mm is not None
        bbox_w, bbox_h = _design_bbox(polylines, workpiece_size_mm)
        wp = _workpiece_polyline(bbox_w, bbox_h)
        polylines = [wp, *polylines]

    groups = group_with_holes(polylines)
    rings_per_group: list[list[Polyline]] = []
    for group in groups:
        rings = _cascade_offsets(group, radius, step_over_mm)
        shifted = [
            Polyline(points=tuple((x + ox, y + oy) for x, y in r.points), closed=True)
            for r in rings
        ]
        if shifted:
            rings_per_group.append(shifted)

    moves: list[Move] = []
    for z in z_levels:
        for rings in rings_per_group:
            for ring in rings:
                moves.extend(_trace_polyline(ring, z, safe_z))
    return moves


def _cascade_offsets(
    group: PolygonWithHoles, radius_mm: float, step_over_mm: float
) -> list[Polyline]:
    """Inward offset cascade of one polygon-with-holes."""
    outer_scaled = _scale(ensure_ccw(group.outer.points))
    holes_scaled = [_scale(ensure_cw(h.points)) for h in group.holes]

    pco = pyclipper.PyclipperOffset()
    pco.ArcTolerance = _CLIPPER_ARC_TOL
    pco.AddPath(outer_scaled, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    for hole in holes_scaled:
        pco.AddPath(hole, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)

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


def _scale(points: tuple[tuple[float, float], ...]) -> list[tuple[int, int]]:
    scaled = [(round(x * _CLIPPER_SCALE), round(y * _CLIPPER_SCALE)) for x, y in points]
    if len(scaled) >= 2 and scaled[-1] == scaled[0]:
        scaled = scaled[:-1]
    return scaled


def _design_bbox(
    polylines: list[Polyline], workpiece_size_mm: tuple[float, float]
) -> tuple[float, float]:
    """Return the workpiece dimensions. The artwork is expected to fit inside
    a (0, 0) → (W, H) rectangle; this helper just unpacks the tuple but
    leaves room for a future "fit to bbox" mode without touching callers."""
    w, h = workpiece_size_mm
    if w <= 0 or h <= 0:
        raise ValueError("workpiece_size_mm components must be positive")
    return w, h


def _workpiece_polyline(width_mm: float, height_mm: float) -> Polyline:
    """A CCW rectangle from (0, 0) to (width, height)."""
    return Polyline(
        points=(
            (0.0, 0.0),
            (width_mm, 0.0),
            (width_mm, height_mm),
            (0.0, height_mm),
        ),
        closed=True,
    )
