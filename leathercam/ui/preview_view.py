"""QGraphicsView subclass with mouse-wheel zoom and middle-button pan.

Used for both the top-down (2-D) and isometric (3-D) toolpath previews.
The view doesn't know which projection is on the scene — it just gives
the user a way to look around.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsView


class PreviewView(QGraphicsView):
    _ZOOM_STEP = 1.15
    _MIN_SCALE = 0.05
    _MAX_SCALE = 2000.0

    # Emitted when the user drags with the left mouse button while
    # rotation_enabled is True. MainWindow updates yaw/pitch and re-renders.
    rotated = Signal(int, int)

    def __init__(self, scene=None, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self._panning = False
        self._pan_start: QPoint | None = None
        self._rotating = False
        self._rotate_start: QPoint | None = None
        self.rotation_enabled = False

    # --- Zoom ---------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 — Qt override
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        factor = self._ZOOM_STEP if delta > 0 else 1.0 / self._ZOOM_STEP
        current = self.transform().m11()
        next_scale = abs(current) * factor
        if next_scale < self._MIN_SCALE or next_scale > self._MAX_SCALE:
            event.accept()
            return
        self.scale(factor, factor)
        event.accept()

    # --- Pan ----------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        is_left = event.button() == Qt.MouseButton.LeftButton
        is_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton) or (
            is_left and is_shift
        ):
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if is_left and self.rotation_enabled:
            self._rotating = True
            self._rotate_start = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and self._pan_start is not None:
            new_pos = event.position().toPoint()
            delta = new_pos - self._pan_start
            self._pan_start = new_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return
        if self._rotating and self._rotate_start is not None:
            new_pos = event.position().toPoint()
            delta = new_pos - self._rotate_start
            self._rotate_start = new_pos
            if delta.x() or delta.y():
                self.rotated.emit(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self._pan_start = None
            self.viewport().unsetCursor()
            event.accept()
            return
        if self._rotating and event.button() == Qt.MouseButton.LeftButton:
            self._rotating = False
            self._rotate_start = None
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # --- Reset --------------------------------------------------------------

    def fit_scene(self, padding: float = 0.05) -> None:
        rect = self.scene().itemsBoundingRect()
        if rect.isEmpty():
            return
        rect.adjust(
            -rect.width() * padding,
            -rect.height() * padding,
            rect.width() * padding,
            rect.height() * padding,
        )
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def reset_zoom(self) -> None:
        self.resetTransform()
        # Re-apply Y-flip so machine Y still goes up on screen.
        self.scale(1.0, -1.0)
        self.fit_scene()

    def event(self, event: QEvent) -> bool:
        # Double-click anywhere fits the scene; convenient when zoomed out.
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self.fit_scene()
            return True
        return super().event(event)

    def map_to_machine(self, screen_point: QPoint) -> QPointF:
        """Convert a viewport pixel to scene/machine coordinates."""
        return self.mapToScene(screen_point)
