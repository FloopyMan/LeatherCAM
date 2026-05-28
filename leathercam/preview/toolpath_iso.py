"""Isometric 3-D preview of a toolpath.

The strategy avoids OpenGL / Qt 3D so the same QGraphicsScene that
powers the 2-D top-down view can render an isometric projection too.
Pan and zoom come from the existing QGraphicsView; the only
projection-specific code is the (x, y, z) → (screen_x, screen_y)
mapping that turns a 3-D move list into 2-D line items.

The projection matches the convention most CAM viewers use:

    +X goes 30° below horizontal to the right,
    +Y goes 30° below horizontal to the left,
    +Z is straight up.

Cuts are red, rapids are grey dashed. An optional workpiece argument
draws a wireframe box that gives the scene a stable frame of reference.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QLineF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsScene

from leathercam.gcode import Move

_RAPID_COLOR = QColor(180, 180, 180)
_CUT_COLOR = QColor(220, 60, 60)
_FRAME_COLOR = QColor(110, 110, 110)

_COS_30 = math.cos(math.radians(30))
_SIN_30 = math.sin(math.radians(30))


def project(point: tuple[float, float, float]) -> tuple[float, float]:
    """Map a 3-D point in machine coordinates to a 2-D scene point."""
    x, y, z = point
    sx = x * _COS_30 - y * _COS_30
    sy = -x * _SIN_30 - y * _SIN_30 + z
    return (sx, sy)


def render_toolpath_iso(
    scene: QGraphicsScene,
    moves: Iterable[Move],
    raster_width_mm: float | None = None,
    raster_height_mm: float | None = None,
    raster_depth_mm: float | None = None,
) -> None:
    """Clear the scene and draw an isometric projection of the toolpath.

    raster_width_mm, raster_height_mm — XY footprint of the workpiece
    (optional). If raster_depth_mm is also given, the workpiece is drawn
    as a full wireframe box; otherwise just the top rectangle.
    """
    scene.clear()

    if raster_width_mm and raster_height_mm:
        _draw_workpiece(scene, raster_width_mm, raster_height_mm, raster_depth_mm)

    rapid_pen = QPen(_RAPID_COLOR)
    rapid_pen.setStyle(rapid_pen.style().DashLine)
    rapid_pen.setCosmetic(True)
    cut_pen = QPen(_CUT_COLOR)
    cut_pen.setCosmetic(True)
    cut_pen.setWidth(2)

    prev: Move | None = None
    for move in moves:
        if prev is not None:
            p0 = project((prev.x, prev.y, prev.z))
            p1 = project((move.x, move.y, move.z))
            if p0 != p1:
                pen = rapid_pen if move.rapid else cut_pen
                scene.addLine(QLineF(p0[0], p0[1], p1[0], p1[1]), pen)
        prev = move


def _draw_workpiece(
    scene: QGraphicsScene,
    w: float,
    h: float,
    depth: float | None,
) -> None:
    frame_pen = QPen(_FRAME_COLOR)
    frame_pen.setCosmetic(True)
    top = [(0.0, 0.0, 0.0), (w, 0.0, 0.0), (w, h, 0.0), (0.0, h, 0.0)]
    _draw_loop(scene, top, frame_pen)
    if depth and depth > 0:
        bottom = [(x, y, -depth) for (x, y, _) in top]
        _draw_loop(scene, bottom, frame_pen)
        for top_pt, bot_pt in zip(top, bottom, strict=True):
            _draw_segment(scene, top_pt, bot_pt, frame_pen)


def _draw_loop(
    scene: QGraphicsScene,
    pts: list[tuple[float, float, float]],
    pen: QPen,
) -> None:
    for i in range(len(pts)):
        _draw_segment(scene, pts[i], pts[(i + 1) % len(pts)], pen)


def _draw_segment(
    scene: QGraphicsScene,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    pen: QPen,
) -> None:
    pa = project(a)
    pb = project(b)
    scene.addLine(QLineF(pa[0], pa[1], pb[0], pb[1]), pen)
