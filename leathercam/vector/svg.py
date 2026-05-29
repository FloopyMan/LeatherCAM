"""SVG importer.

Parses an SVG file with svgelements, flattens curves and arcs into polylines,
and returns coordinates in millimeters. svgelements normalises everything to
pixel coordinates at 96 DPI, so the final scale is 25.4 / 96 mm per pixel.

The Y axis is flipped on output so the result matches the rest of the
project's "Y up" convention (machine coordinates).
"""

from __future__ import annotations

import math
from pathlib import Path

from svgelements import (
    SVG,
    Arc,
    Close,
    CubicBezier,
    Line,
    Move,
    QuadraticBezier,
    Shape,
)
from svgelements import Path as SvgPath

from leathercam.vector.types import Polyline

_MM_PER_PX = 25.4 / 96.0


def load_svg(source: str | Path, max_segment_mm: float = 0.2) -> list[Polyline]:
    """Read an SVG file and return its geometry as polylines in millimeters.

    max_segment_mm — maximum length of a straight segment used to approximate
    a curve or arc. Smaller values give smoother contours at the cost of
    more G-code.
    """
    if max_segment_mm <= 0:
        raise ValueError("max_segment_mm must be positive")

    svg = SVG.parse(source, ppi=96)
    bbox_height_mm = float(svg.height) * _MM_PER_PX
    polylines: list[Polyline] = []
    for element in svg.elements():
        if not isinstance(element, Shape):
            continue
        path = SvgPath(element)
        polylines.extend(_flatten_path(path, max_segment_mm, bbox_height_mm))
    return polylines


def _flatten_path(path: SvgPath, max_segment_mm: float, bbox_height_mm: float) -> list[Polyline]:
    """Walk a single svgelements Path and split it into one or more Polylines."""
    polylines: list[Polyline] = []
    current: list[tuple[float, float]] = []
    start_point: tuple[float, float] | None = None

    def flush(closed: bool) -> None:
        if len(current) >= 2:
            polylines.append(Polyline(points=tuple(current), closed=closed))
        current.clear()

    for segment in path.segments():
        if isinstance(segment, Move):
            flush(False)
            pt = _to_mm(segment.end, bbox_height_mm)
            current.append(pt)
            start_point = pt
        elif isinstance(segment, Line):
            current.append(_to_mm(segment.end, bbox_height_mm))
        elif isinstance(segment, (CubicBezier, QuadraticBezier, Arc)):
            current.extend(_sample(segment, max_segment_mm, bbox_height_mm))
        elif isinstance(segment, Close):
            if start_point is not None:
                current.append(start_point)
            flush(True)
            start_point = None
    flush(False)
    return polylines


def _to_mm(point: object, bbox_height_mm: float) -> tuple[float, float]:
    x_mm = float(point.x) * _MM_PER_PX
    y_mm = bbox_height_mm - float(point.y) * _MM_PER_PX
    return (x_mm, y_mm)


def _sample(
    segment: object, max_segment_mm: float, bbox_height_mm: float
) -> list[tuple[float, float]]:
    """Adaptive sampling: choose N from segment length in mm."""
    length_px = float(segment.length(error=1e-3))
    length_mm = length_px * _MM_PER_PX
    n = max(2, math.ceil(length_mm / max_segment_mm))
    return [_to_mm(segment.point(i / n), bbox_height_mm) for i in range(1, n + 1)]
