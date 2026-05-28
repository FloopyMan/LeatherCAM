"""2-D preview rendering for toolpaths.

Draws rapid moves and cutting moves onto a QGraphicsScene. The scene uses
machine coordinates (mm) directly; the QGraphicsView flips Y so the
preview matches the bed orientation (Y up).
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QLineF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsScene

from leathercam.gcode import Move

_RAPID_COLOR = QColor(180, 180, 180)
_CUT_COLOR = QColor(220, 60, 60)


def render_toolpath(
    scene: QGraphicsScene,
    moves: Iterable[Move],
    raster_width_mm: float | None = None,
    raster_height_mm: float | None = None,
) -> None:
    """Clear the scene and redraw the given toolpath.

    Optional raster_width_mm and raster_height_mm draw the workpiece outline.
    """
    scene.clear()

    if raster_width_mm and raster_height_mm:
        outline_pen = QPen(QColor(100, 100, 100))
        outline_pen.setCosmetic(True)
        scene.addRect(0.0, 0.0, raster_width_mm, raster_height_mm, outline_pen)

    rapid_pen = QPen(_RAPID_COLOR)
    rapid_pen.setStyle(rapid_pen.style().DashLine)
    rapid_pen.setCosmetic(True)
    cut_pen = QPen(_CUT_COLOR)
    cut_pen.setCosmetic(True)
    cut_pen.setWidth(2)

    prev: Move | None = None
    for move in moves:
        if prev is not None and (prev.x != move.x or prev.y != move.y):
            pen = rapid_pen if move.rapid else cut_pen
            scene.addLine(QLineF(prev.x, prev.y, move.x, move.y), pen)
        prev = move
