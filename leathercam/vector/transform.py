"""Geometric transforms on polyline collections."""

from __future__ import annotations

from leathercam.vector.types import Polyline


def polylines_bbox(
    polylines: list[Polyline],
) -> tuple[float, float, float, float] | None:
    """Combined bounding box (min_x, min_y, max_x, max_y) or None if empty."""
    if not polylines:
        return None
    xs = [p[0] for poly in polylines for p in poly.points]
    ys = [p[1] for poly in polylines for p in poly.points]
    return (min(xs), min(ys), max(xs), max(ys))


def scale_polylines(
    polylines: list[Polyline], sx: float, sy: float | None = None
) -> list[Polyline]:
    """Scale every point by (sx, sy). When sy is None, scales uniformly by sx."""
    if sx <= 0:
        raise ValueError("sx must be positive")
    if sy is None:
        sy = sx
    if sy <= 0:
        raise ValueError("sy must be positive")
    return [
        Polyline(points=tuple((x * sx, y * sy) for x, y in poly.points), closed=poly.closed)
        for poly in polylines
    ]


def fit_polylines(
    polylines: list[Polyline],
    target_width_mm: float,
    target_height_mm: float | None = None,
    *,
    keep_aspect: bool = True,
) -> list[Polyline]:
    """Resize polylines so their combined bbox matches the requested dimensions.

    keep_aspect=True (default) ignores target_height_mm and uses the same
    factor on both axes; the actual output height is target_width_mm × the
    original aspect ratio. keep_aspect=False scales the axes independently.
    """
    if target_width_mm <= 0:
        raise ValueError("target_width_mm must be positive")
    bbox = polylines_bbox(polylines)
    if bbox is None:
        return []
    cur_w = bbox[2] - bbox[0]
    cur_h = bbox[3] - bbox[1]
    if cur_w <= 0 or cur_h <= 0:
        return polylines
    sx = target_width_mm / cur_w
    if keep_aspect or target_height_mm is None:
        sy = sx
    else:
        if target_height_mm <= 0:
            raise ValueError("target_height_mm must be positive")
        sy = target_height_mm / cur_h
    return scale_polylines(polylines, sx, sy)


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
