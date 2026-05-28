"""Toolpath analytics: bounding box, time estimate, machine-bounds check.

These helpers stay free of Qt so they can be unit-tested headlessly and
reused from CLI tooling.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from leathercam.gcode import Move

# CNC 3018 effective travel — used as the default bounds check window.
CNC_3018_BOUNDS_MM = (300.0, 180.0, 45.0)


@dataclass(frozen=True)
class BoundingBox:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def height(self) -> float:
        return self.max_z - self.min_z


def bounding_box(moves: Iterable[Move]) -> BoundingBox | None:
    """Return the 3-D extent of the toolpath, or None if there are no moves."""
    moves = list(moves)
    if not moves:
        return None
    xs = [m.x for m in moves]
    ys = [m.y for m in moves]
    zs = [m.z for m in moves]
    return BoundingBox(
        min_x=min(xs),
        min_y=min(ys),
        min_z=min(zs),
        max_x=max(xs),
        max_y=max(ys),
        max_z=max(zs),
    )


def estimate_duration_minutes(
    moves: Iterable[Move],
    *,
    feed_xy: float,
    feed_z: float,
    rapid_feed: float = 2000.0,
) -> float:
    """Sum each segment's length divided by its effective feedrate.

    Mirrors the postprocessor's feed-selection rule: rapid moves use
    rapid_feed; pure plunges use feed_z; everything else uses feed_xy.
    Returns the total in minutes (feeds are mm/min).
    """
    moves = list(moves)
    if len(moves) < 2:
        return 0.0
    total = 0.0
    for prev, cur in pairwise(moves):
        dx = cur.x - prev.x
        dy = cur.y - prev.y
        dz = cur.z - prev.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance == 0.0:
            continue
        if cur.rapid:
            feed = rapid_feed
        elif cur.x == prev.x and cur.y == prev.y and cur.z != prev.z:
            feed = feed_z
        else:
            feed = feed_xy
        total += distance / feed
    return total


def exceeds_bounds(
    bbox: BoundingBox | None,
    *,
    machine: tuple[float, float, float] = CNC_3018_BOUNDS_MM,
    safe_z: float = 0.0,
) -> list[str]:
    """Return human-readable warnings for axes that go out of range.

    The safe_z argument is the maximum Z the user expects above the
    workpiece; the check allows Z up to safe_z and down to -machine_z.
    """
    if bbox is None:
        return []
    mx, my, mz = machine
    warnings: list[str] = []
    if bbox.min_x < 0:
        warnings.append(f"X выходит за 0 (мин. {bbox.min_x:.2f} мм)")
    if bbox.max_x > mx:
        warnings.append(f"X выходит за {mx:.0f} мм (макс. {bbox.max_x:.2f} мм)")
    if bbox.min_y < 0:
        warnings.append(f"Y выходит за 0 (мин. {bbox.min_y:.2f} мм)")
    if bbox.max_y > my:
        warnings.append(f"Y выходит за {my:.0f} мм (макс. {bbox.max_y:.2f} мм)")
    if bbox.min_z < -mz:
        warnings.append(f"Z уходит глубже {-mz:.0f} мм (мин. {bbox.min_z:.2f} мм)")
    if bbox.max_z > safe_z + 0.001:
        warnings.append(
            f"Z поднимается выше safe Z (макс. {bbox.max_z:.2f}, ожидалось ≤ {safe_z:.2f})"
        )
    return warnings
