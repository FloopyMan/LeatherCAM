"""Main application window — stages 1-2 UI.

Layout: parameter form on the left, toolpath preview on the right. The
window owns the currently loaded input (image or polylines) and rebuilds
the preview on demand. G-code generation runs synchronously for now;
long jobs will be moved to a worker thread in a later stage.

Two strategies are supported:
- Растровая: raster zigzag over a binarized image (PNG/JPG/BMP).
- Контурная: profile (offset-able) traversal of polylines (SVG/DXF).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from leathercam.job import (
    JobParameters,
    ProfileJobParameters,
    build_moves,
    build_profile_moves,
    build_raster,
    generate_gcode,
    generate_profile_gcode,
)
from leathercam.preview import render_toolpath
from leathercam.vector import Polyline, load_dxf, load_svg

logger = logging.getLogger(__name__)

STRATEGY_RASTER = "raster"
STRATEGY_PROFILE = "profile"


class _Parameters(QWidget):
    """Left-hand parameter form. Toggles section visibility by strategy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        strategy_box = QGroupBox("Стратегия")
        strategy_form = QFormLayout(strategy_box)
        self.strategy = QComboBox()
        self.strategy.addItem("Растровая (PNG/JPG)", STRATEGY_RASTER)
        self.strategy.addItem("Контурная (SVG/DXF)", STRATEGY_PROFILE)
        self.strategy.currentIndexChanged.connect(self._sync_visibility)
        strategy_form.addRow("Тип:", self.strategy)

        self.image_box = QGroupBox("Изображение")
        image_form = QFormLayout(self.image_box)
        self.target_width = self._double(1.0, 300.0, 60.0, 0.1, " мм")
        self.pixel_size = self._double(0.05, 5.0, 0.2, 0.05, " мм")
        self.threshold = self._int(0, 255, 128)
        self.invert = QCheckBox("Инвертировать (резать светлое)")
        image_form.addRow("Ширина клише:", self.target_width)
        image_form.addRow("Шаг (= step-over):", self.pixel_size)
        image_form.addRow("Порог бинаризации:", self.threshold)
        image_form.addRow(self.invert)

        self.vector_box = QGroupBox("Вектор и фреза")
        vector_form = QFormLayout(self.vector_box)
        self.tool_diameter = self._double(0.05, 12.0, 1.0, 0.05, " мм")
        self.side = QComboBox()
        self.side.addItems(["on", "inside", "outside"])
        vector_form.addRow("Диаметр фрезы:", self.tool_diameter)
        vector_form.addRow("Сторона:", self.side)

        cut_box = QGroupBox("Глубина")
        cut_form = QFormLayout(cut_box)
        self.depth = self._double(0.05, 10.0, 0.4, 0.05, " мм")
        self.step_down = self._double(0.05, 5.0, 0.2, 0.05, " мм")
        cut_form.addRow("Глубина:", self.depth)
        cut_form.addRow("Глубина за проход:", self.step_down)

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

        layout.addWidget(strategy_box)
        layout.addWidget(self.image_box)
        layout.addWidget(self.vector_box)
        layout.addWidget(cut_box)
        layout.addWidget(machine_box)
        layout.addStretch(1)

        self._sync_visibility()

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

    def _sync_visibility(self) -> None:
        strategy = self.strategy.currentData()
        self.image_box.setVisible(strategy == STRATEGY_RASTER)
        self.vector_box.setVisible(strategy == STRATEGY_PROFILE)

    def current_strategy(self) -> str:
        return str(self.strategy.currentData())

    def set_strategy(self, strategy: str) -> None:
        for i in range(self.strategy.count()):
            if self.strategy.itemData(i) == strategy:
                self.strategy.setCurrentIndex(i)
                return

    def to_raster_parameters(self) -> JobParameters:
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

    def to_profile_parameters(self) -> ProfileJobParameters:
        return ProfileJobParameters(
            tool_diameter_mm=float(self.tool_diameter.value()),
            side=self.side.currentText(),  # type: ignore[arg-type]
            depth_mm=float(self.depth.value()),
            step_down_mm=float(self.step_down.value()),
            feed_xy=float(self.feed_xy.value()),
            feed_z=float(self.feed_z.value()),
            spindle_rpm=int(self.spindle_rpm.value()),
            safe_z=float(self.safe_z.value()),
        )

    # Back-compat for stage 1 tests.
    def to_job_parameters(self) -> JobParameters:
        return self.to_raster_parameters()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LeatherCAM")
        self.resize(1280, 800)

        self._image: Image.Image | None = None
        self._polylines: list[Polyline] = []
        self._source_path: Path | None = None

        self.params = _Parameters()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(Qt.GlobalColor.white)
        self.view.scale(1.0, -1.0)

        self.status_label = QLabel("Откройте изображение или вектор для начала.")
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
        splitter.setSizes([380, 900])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.setStatusBar(QStatusBar(self))

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Файл")

        open_img = QAction("Открыть &изображение…", self)
        open_img.setShortcut("Ctrl+O")
        open_img.triggered.connect(self._on_open_image)
        file_menu.addAction(open_img)

        open_vec = QAction("Открыть &вектор (SVG/DXF)…", self)
        open_vec.setShortcut("Ctrl+Shift+O")
        open_vec.triggered.connect(self._on_open_vector)
        file_menu.addAction(open_vec)

        file_menu.addSeparator()

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
        self._polylines = []
        self._source_path = path
        self.params.set_strategy(STRATEGY_RASTER)
        self.status_label.setText(f"Загружено: {path.name} ({image.width}×{image.height} px)")
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._on_preview()

    def _on_open_vector(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть вектор",
            "",
            "Вектор (*.svg *.dxf);;SVG (*.svg);;DXF (*.dxf);;Все файлы (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        suffix = path.suffix.lower()
        try:
            if suffix == ".svg":
                polylines = load_svg(path)
            elif suffix == ".dxf":
                polylines = load_dxf(path)
            else:
                QMessageBox.warning(
                    self, "Неизвестный формат", f"Расширение {suffix!r} не поддержано"
                )
                return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать вектор: {exc}")
            return
        if not polylines:
            QMessageBox.warning(self, "Пусто", "В файле не нашлось геометрии.")
            return
        self._image = None
        self._polylines = polylines
        self._source_path = path
        self.params.set_strategy(STRATEGY_PROFILE)
        self.status_label.setText(f"Загружено: {path.name} ({len(polylines)} полилиний)")
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._on_preview()

    def _on_preview(self) -> None:
        strategy = self.params.current_strategy()
        try:
            if strategy == STRATEGY_RASTER and self._image is not None:
                params = self.params.to_raster_parameters()
                raster = build_raster(self._image, params)
                moves = build_moves(raster, params)
                w, h = raster.width_mm, raster.height_mm
                size_text = f"{w:.1f}×{h:.1f} мм"
            elif strategy == STRATEGY_PROFILE and self._polylines:
                params = self.params.to_profile_parameters()
                moves = build_profile_moves(self._polylines, params)
                w = h = None
                size_text = f"полилиний: {len(self._polylines)}"
            else:
                return
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return

        render_toolpath(self.scene, moves, raster_width_mm=w, raster_height_mm=h)
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_label.setText(f"Сегментов траектории: {len(moves)}; {size_text}")

    def _on_generate(self) -> None:
        strategy = self.params.current_strategy()
        try:
            if strategy == STRATEGY_RASTER:
                if self._image is None:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте изображение.")
                    return
                code = generate_gcode(self._image, self.params.to_raster_parameters())
            else:
                if not self._polylines:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте SVG или DXF.")
                    return
                code = generate_profile_gcode(self._polylines, self.params.to_profile_parameters())
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return

        default_name = (self._source_path.stem if self._source_path else "job") + ".gcode"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Сохранить G-code", default_name, "G-code (*.gcode *.nc *.tap);;Все файлы (*)"
        )
        if not path_str:
            return
        Path(path_str).write_text(code, encoding="utf-8")
        self.status_label.setText(f"Сохранено: {path_str}")
