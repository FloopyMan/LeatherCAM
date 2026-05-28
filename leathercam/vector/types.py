"""Common data types for vector input.

A Polyline is the lingua franca between the importers (SVG, DXF) and the
CAM strategies. Coordinates are always in millimeters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Polyline:
    """An ordered sequence of (x, y) points in millimeters.

    closed=True means the last segment connects points[-1] back to points[0]
    even if they are not numerically equal (rendering / CAM treat the loop
    as continuous).
    """

    points: tuple[tuple[float, float], ...]
    closed: bool = False

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Polyline must contain at least two points")

    def length_mm(self) -> float:
        total = 0.0
        for (x0, y0), (x1, y1) in zip(self.points[:-1], self.points[1:], strict=True):
            total += math.hypot(x1 - x0, y1 - y0)
        if self.closed:
            (x0, y0), (x1, y1) = self.points[-1], self.points[0]
            total += math.hypot(x1 - x0, y1 - y0)
        return total

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))
