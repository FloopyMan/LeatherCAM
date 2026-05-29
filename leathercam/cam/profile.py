"""Profile (contour) toolpath strategy.

Follows each input polyline, optionally offset by the tool radius (pyclipper
JT_ROUND). For each Z depth pass, the tool plunges at the first point,
traces the contour, and retracts to safe Z.

Side semantics for closed polylines (assumed CCW for outer boundaries):
- "on"      — tool centerline follows the polyline exactly (engraving).
- "inside"  — tool is offset inward by tool_radius (cut a pocket boundary).
- "outside" — tool is offset outward by tool_radius (cut a part out).

Open polylines always use side="on" — offset is geometrically undefined.
"""

from __future__ import annotations

import math
from typing import Literal

import pyclipper

from leathercam.gcode import Move
from leathercam.vector import Polyline

Side = Literal["on", "inside", "outside"]

_CLIPPER_SCALE = 1000.0
# See leathercam/cam/pocket.py for why we coarsen the default arc tolerance.
_CLIPPER_ARC_TOL = 50.0


def profile(
    polylines: list[Polyline],
    *,
    depth_mm: float,
    step_down_mm: float,
    safe_z: float,
    tool_diameter_mm: float,
    side: Side = "on",
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
    if side not in ("on", "inside", "outside"):
        raise ValueError(f"invalid side: {side!r}")

    radius = tool_diameter_mm / 2.0
    n_passes = math.ceil(depth_mm / step_down_mm)
    z_levels = [-min(step_down_mm * i, depth_mm) for i in range(1, n_passes + 1)]
    ox, oy = origin

    compensated: list[Polyline] = []
    for poly in polylines:
        if side == "on" or not poly.closed:
            compensated.append(poly)
            continue
        delta = radius if side == "outside" else -radius
        compensated.extend(_offset_closed(poly, delta))

    shifted = [
        Polyline(points=tuple((x + ox, y + oy) for x, y in p.points), closed=p.closed)
        for p in compensated
    ]

    moves: list[Move] = []
    for z in z_levels:
        for poly in shifted:
            moves.extend(_trace_polyline(poly, z, safe_z))
    return moves


def _trace_polyline(poly: Polyline, z: float, safe_z: float) -> list[Move]:
    pts = poly.points
    if len(pts) < 2:
        return []
    start_x, start_y = pts[0]
    moves: list[Move] = [
        Move(x=start_x, y=start_y, z=safe_z, rapid=True),
        Move(x=start_x, y=start_y, z=z, rapid=False),
    ]
    for px, py in pts[1:]:
        moves.append(Move(x=px, y=py, z=z, rapid=False))
    end_x, end_y = pts[0] if poly.closed else pts[-1]
    if poly.closed:
        moves.append(Move(x=end_x, y=end_y, z=z, rapid=False))
    moves.append(Move(x=end_x, y=end_y, z=safe_z, rapid=True))
    return moves


def _offset_closed(poly: Polyline, delta_mm: float) -> list[Polyline]:
    """Inflate (positive delta) or deflate (negative) a closed polygon."""
    scaled = [(round(x * _CLIPPER_SCALE), round(y * _CLIPPER_SCALE)) for x, y in poly.points]
    if len(scaled) >= 2 and scaled[-1] == scaled[0]:
        scaled = scaled[:-1]

    pco = pyclipper.PyclipperOffset()
    pco.ArcTolerance = _CLIPPER_ARC_TOL
    pco.AddPath(scaled, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    result = pco.Execute(delta_mm * _CLIPPER_SCALE)

    out: list[Polyline] = []
    for path in result:
        pts = tuple((x / _CLIPPER_SCALE, y / _CLIPPER_SCALE) for x, y in path)
        if len(pts) >= 2:
            out.append(Polyline(points=pts, closed=True))
    return out
