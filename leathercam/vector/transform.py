"""Geometric transforms on polyline collections."""

from __future__ import annotations

from leathercam.vector.types import Polyline


def mirror_x(polylines: list[Polyline]) -> list[Polyline]:
    """Mirror all polylines horizontally around the combined bbox center.

    The bbox stays the same after mirroring, so callers can keep using the
    same origin / placement values.
    """
    if not polylines:
        return []
    min_x = min(p[0] for poly in polylines for p in poly.points)
    max_x = max(p[0] for poly in polylines for p in poly.points)
    sum_x = min_x + max_x
    out: list[Polyline] = []
    for poly in polylines:
        flipped = tuple((sum_x - x, y) for x, y in poly.points)
        out.append(Polyline(points=flipped, closed=poly.closed))
    return out
