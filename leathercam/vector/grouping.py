"""Group closed polylines into outer-with-holes structures.

A glyph like "О" or "Б" is exported by most SVG/DXF tools as two separate
closed contours: the outer outline and the inner hole. Pocketing them
independently is wrong — the hole must remain as material. This module
classifies each closed polyline by nesting depth (via point-in-polygon
tests) and pairs every "outer" with its direct child holes.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon

from leathercam.vector.types import Polyline


@dataclass(frozen=True)
class PolygonWithHoles:
    outer: Polyline
    holes: tuple[Polyline, ...] = ()


def signed_area(points: tuple[tuple[float, float], ...]) -> float:
    n = len(points)
    total = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def ensure_ccw(points: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    return points if signed_area(points) >= 0 else tuple(reversed(points))


def ensure_cw(points: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    return points if signed_area(points) <= 0 else tuple(reversed(points))


def group_with_holes(polylines: list[Polyline]) -> list[PolygonWithHoles]:
    """Classify closed polylines by even/odd nesting depth.

    Polylines at even depth (0, 2, 4...) are treated as outer boundaries;
    odd-depth polylines as holes. Each outer collects the odd-depth
    polylines that sit directly inside it.

    Open polylines and degenerate ones (less than three distinct points)
    are skipped.
    """
    closed = [p for p in polylines if p.closed and len(p.points) >= 3]
    if not closed:
        return []

    polygons: list[Polygon] = []
    valid: list[Polyline] = []
    for p in closed:
        try:
            poly = Polygon(p.points)
        except (ValueError, TypeError):
            continue
        if poly.is_empty or not poly.is_valid:
            poly = poly.buffer(0)
            if poly.is_empty:
                continue
        polygons.append(poly)
        valid.append(p)

    n = len(valid)
    contains = [[False] * n for _ in range(n)]
    depths = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if polygons[j].contains(polygons[i]):
                contains[j][i] = True
                depths[i] += 1

    groups: list[PolygonWithHoles] = []
    for i in range(n):
        if depths[i] % 2 != 0:
            continue
        holes = tuple(valid[j] for j in range(n) if depths[j] == depths[i] + 1 and contains[i][j])
        groups.append(PolygonWithHoles(outer=valid[i], holes=holes))
    return groups
