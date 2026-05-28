"""Main application window — placeholder skeleton (stage 1 will flesh it out)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LeatherCAM")
        self.resize(1200, 800)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.view)

        placeholder = QLabel("LeatherCAM — work in progress (stage 0)")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
