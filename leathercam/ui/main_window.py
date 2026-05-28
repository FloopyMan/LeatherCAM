"""Main application window — stage 1 MVP UI.

Layout: parameter form on the left, toolpath preview on the right. The
window owns the currently loaded PIL image and rebuilds the preview on
demand. G-code generation runs synchronously for now; long jobs will be
moved to a worker thread in a later stage.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from leathercam.job import JobParameters, build_moves, build_raster, generate_gcode
from leathercam.preview import render_toolpath

logger = logging.getLogger(__name__)


class _Parameters(QWidget):
    """Left-hand parameter form."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        image_box = QGroupBox("Изображение")
        image_form = QFormLayout(image_box)
        self.target_width = self._double(1.0, 300.0, 60.0, 0.1, " мм")
        self.pixel_size = self._double(0.05, 5.0, 0.2, 0.05, " мм")
        self.threshold = self._int(0, 255, 128)
        self.invert = QCheckBox("Инвертировать (резать светлое)")
        image_form.addRow("Ширина клише:", self.target_width)
        image_form.addRow("Шаг (= step-over):", self.pixel_size)
        image_form.addRow("Порог бинаризации:", self.threshold)
        image_form.addRow(self.invert)

        tool_box = QGroupBox("Фреза и проход")
        tool_form = QFormLayout(tool_box)
        self.depth = self._double(0.05, 10.0, 0.4, 0.05, " мм")
        self.step_down = self._double(0.05, 5.0, 0.2, 0.05, " мм")
        tool_form.addRow("Глубина:", self.depth)
        tool_form.addRow("Глубина за проход:", self.step_down)

        machine_box = QGroupBox("Станок")
        machine_form = QFormLayout(machine_box)
        self.feed_xy = self._double(50.0, 5000.0, 600.0, 50.0, " мм/мин")
        self.feed_z = self._double(20.0, 2000.0, 200.0, 10.0, " мм/мин")
        self.spindle_rpm = self._int(1000, 30000, 10000)
        self.safe_z = self._double(0.5, 50.0, 5.0, 0.5, " мм")
        machine_form.addRow("Подача XY:", self.feed_xy)
        machine_form.addRow("Подача Z:", self.feed_z)
        machine_form.addRow("Обороты шпинделя:", self.spindle_rpm)
        machine_form.addRow("Safe Z:", self.safe_z)

        layout.addWidget(image_box)
        layout.addWidget(tool_box)
        layout.addWidget(machine_box)
        layout.addStretch(1)

    def _double(
        self, lo: float, hi: float, value: float, step: float, suffix: str
    ) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(lo, hi)
        box.setSingleStep(step)
        box.setDecimals(3)
        box.setValue(value)
        box.setSuffix(suffix)
        return box

    def _int(self, lo: int, hi: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(lo, hi)
        box.setValue(value)
        return box

    def to_job_parameters(self) -> JobParameters:
        return JobParameters(
            target_width_mm=float(self.target_width.value()),
            pixel_size_mm=float(self.pixel_size.value()),
            threshold=int(self.threshold.value()),
            invert=bool(self.invert.isChecked()),
            depth_mm=float(self.depth.value()),
            step_down_mm=float(self.step_down.value()),
            feed_xy=float(self.feed_xy.value()),
            feed_z=float(self.feed_z.value()),
            spindle_rpm=int(self.spindle_rpm.value()),
            safe_z=float(self.safe_z.value()),
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LeatherCAM")
        self.resize(1280, 800)

        self._image: Image.Image | None = None
        self._image_path: Path | None = None

        self.params = _Parameters()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(Qt.GlobalColor.white)
        self.view.scale(1.0, -1.0)

        self.status_label = QLabel("Откройте изображение для начала.")
        self.preview_button = QPushButton("Обновить предпросмотр")
        self.preview_button.clicked.connect(self._on_preview)
        self.generate_button = QPushButton("Сгенерировать G-code…")
        self.generate_button.clicked.connect(self._on_generate)
        self.generate_button.setEnabled(False)
        self.preview_button.setEnabled(False)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.addWidget(self.view, stretch=1)
        right_layout.addWidget(self.preview_button)
        right_layout.addWidget(self.generate_button)
        right_layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.params)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 920])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.setStatusBar(QStatusBar(self))

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Файл")
        open_action = QAction("&Открыть изображение…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_image)
        file_menu.addAction(open_action)

        save_action = QAction("&Сохранить G-code…", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_generate)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        quit_action = QAction("&Выход", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _on_open_image(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp);;Все файлы (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            image = Image.open(path)
            image.load()
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {exc}")
            return
        self._image = image
        self._image_path = path
        self.status_label.setText(f"Загружено: {path.name} ({image.width}×{image.height} px)")
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._on_preview()

    def _on_preview(self) -> None:
        if self._image is None:
            return
        try:
            params = self.params.to_job_parameters()
            raster = build_raster(self._image, params)
            moves = build_moves(raster, params)
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return
        render_toolpath(
            self.scene,
            moves,
            raster_width_mm=raster.width_mm,
            raster_height_mm=raster.height_mm,
        )
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_label.setText(
            f"Сегментов траектории: {len(moves)}; размер: "
            f"{raster.width_mm:.1f}×{raster.height_mm:.1f} мм"
        )

    def _on_generate(self) -> None:
        if self._image is None:
            QMessageBox.information(self, "Нет изображения", "Сначала откройте изображение.")
            return
        try:
            params = self.params.to_job_parameters()
            code = generate_gcode(self._image, params)
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return

        default_name = (self._image_path.stem if self._image_path else "job") + ".gcode"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Сохранить G-code", default_name, "G-code (*.gcode *.nc *.tap);;Все файлы (*)"
        )
        if not path_str:
            return
        Path(path_str).write_text(code, encoding="utf-8")
        self.status_label.setText(f"Сохранено: {path_str}")
