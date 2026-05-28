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
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from leathercam.cam import bounding_box, estimate_duration_minutes, exceeds_bounds
from leathercam.gcode import Move
from leathercam.job import (
    JobParameters,
    PocketJobParameters,
    ProfileJobParameters,
    VCarveJobParameters,
    build_moves,
    build_pocket_moves,
    build_profile_moves,
    build_raster,
    build_vcarve_moves,
    generate_gcode,
    generate_pocket_gcode,
    generate_profile_gcode,
    generate_vcarve_gcode,
)
from leathercam.preview import render_toolpath
from leathercam.profiles import Material, Tool, load_materials, load_tools
from leathercam.vector import Polyline, load_dxf, load_svg

logger = logging.getLogger(__name__)

STRATEGY_RASTER = "raster"
STRATEGY_PROFILE = "profile"
STRATEGY_POCKET = "pocket"
STRATEGY_VCARVE = "vcarve"


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
        self.strategy.addItem("Карман (SVG/DXF, выборка фона)", STRATEGY_POCKET)
        self.strategy.addItem("V-carve (PNG/JPG, V-фреза)", STRATEGY_VCARVE)
        self.strategy.currentIndexChanged.connect(self._sync_visibility)
        strategy_form.addRow("Тип:", self.strategy)

        profile_box = QGroupBox("Профиль материала и фрезы")
        profile_form = QFormLayout(profile_box)
        self._materials: list[Material] = load_materials()
        self._tools: list[Tool] = load_tools()
        self.material_combo = QComboBox()
        for material in self._materials:
            self.material_combo.addItem(material.name, material.id)
        self.tool_combo = QComboBox()
        for tool in self._tools:
            self.tool_combo.addItem(tool.name, tool.id)
        self.apply_recommended = QPushButton("Применить рекомендованные параметры")
        self.apply_recommended.clicked.connect(self._on_apply_recommended)
        profile_form.addRow("Материал:", self.material_combo)
        profile_form.addRow("Фреза:", self.tool_combo)
        profile_form.addRow(self.apply_recommended)

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
        self.step_over = self._double(0.05, 5.0, 0.5, 0.05, " мм")
        self.pocket_mode = QComboBox()
        self.pocket_mode.addItem("Карман: фрезеровать рисунок", "design")
        self.pocket_mode.addItem("Карман: фрезеровать фон (оставить рисунок)", "background")
        self.workpiece_w = self._double(1.0, 500.0, 60.0, 1.0, " мм")
        self.workpiece_h = self._double(1.0, 500.0, 40.0, 1.0, " мм")
        vector_form.addRow("Диаметр фрезы:", self.tool_diameter)
        vector_form.addRow("Сторона (Profile):", self.side)
        vector_form.addRow("Шаг (step-over, Pocket):", self.step_over)
        vector_form.addRow("Режим (Pocket):", self.pocket_mode)
        vector_form.addRow("Размер клише, ширина:", self.workpiece_w)
        vector_form.addRow("Размер клише, высота:", self.workpiece_h)

        self.vcarve_box = QGroupBox("V-carve")
        vcarve_form = QFormLayout(self.vcarve_box)
        self.v_angle = self._double(10.0, 170.0, 60.0, 5.0, "°")
        self.v_max_depth = self._double(0.1, 20.0, 2.0, 0.1, " мм")
        vcarve_form.addRow("Угол V-фрезы:", self.v_angle)
        vcarve_form.addRow("Макс. глубина:", self.v_max_depth)

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

        stamp_box = QGroupBox("Клише")
        stamp_form = QFormLayout(stamp_box)
        self.mirror_x = QCheckBox("Зеркалить по X (для штампа)")
        stamp_form.addRow(self.mirror_x)

        layout.addWidget(strategy_box)
        layout.addWidget(profile_box)
        layout.addWidget(self.image_box)
        layout.addWidget(self.vector_box)
        layout.addWidget(self.vcarve_box)
        layout.addWidget(cut_box)
        layout.addWidget(stamp_box)
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
        self.image_box.setVisible(strategy in (STRATEGY_RASTER, STRATEGY_VCARVE))
        self.vector_box.setVisible(strategy in (STRATEGY_PROFILE, STRATEGY_POCKET))
        self.vcarve_box.setVisible(strategy == STRATEGY_VCARVE)

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
            mirror_x=bool(self.mirror_x.isChecked()),
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
            mirror_x=bool(self.mirror_x.isChecked()),
        )

    def to_vcarve_parameters(self) -> VCarveJobParameters:
        return VCarveJobParameters(
            target_width_mm=float(self.target_width.value()),
            pixel_size_mm=float(self.pixel_size.value()),
            threshold=int(self.threshold.value()),
            invert=bool(self.invert.isChecked()),
            v_angle_deg=float(self.v_angle.value()),
            max_depth_mm=float(self.v_max_depth.value()),
            step_down_mm=float(self.step_down.value()),
            feed_xy=float(self.feed_xy.value()),
            feed_z=float(self.feed_z.value()),
            spindle_rpm=int(self.spindle_rpm.value()),
            safe_z=float(self.safe_z.value()),
            mirror_x=bool(self.mirror_x.isChecked()),
        )

    def to_pocket_parameters(self) -> PocketJobParameters:
        return PocketJobParameters(
            tool_diameter_mm=float(self.tool_diameter.value()),
            step_over_mm=float(self.step_over.value()),
            depth_mm=float(self.depth.value()),
            step_down_mm=float(self.step_down.value()),
            feed_xy=float(self.feed_xy.value()),
            feed_z=float(self.feed_z.value()),
            spindle_rpm=int(self.spindle_rpm.value()),
            safe_z=float(self.safe_z.value()),
            mode=self.pocket_mode.currentData(),
            workpiece_size_mm=(
                float(self.workpiece_w.value()),
                float(self.workpiece_h.value()),
            ),
            mirror_x=bool(self.mirror_x.isChecked()),
        )

    # Back-compat for stage 1 tests.
    def to_job_parameters(self) -> JobParameters:
        return self.to_raster_parameters()

    def _on_apply_recommended(self) -> None:
        material_id = self.material_combo.currentData()
        tool_id = self.tool_combo.currentData()
        material = next((m for m in self._materials if m.id == material_id), None)
        tool = next((t for t in self._tools if t.id == tool_id), None)
        if material is None or tool is None:
            return
        if tool.kind != "vbit":
            self.tool_diameter.setValue(tool.diameter_mm)
        if tool.kind == "vbit" and tool.angle_deg is not None:
            self.v_angle.setValue(tool.angle_deg)
        rec = material.recommendation_for(tool.id)
        if rec is None:
            return
        self.feed_xy.setValue(rec.feed_xy)
        self.feed_z.setValue(rec.feed_z)
        self.spindle_rpm.setValue(rec.spindle_rpm)
        self.step_down.setValue(rec.step_down_mm)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LeatherCAM")
        self.resize(1280, 800)

        self._image: Image.Image | None = None
        self._polylines: list[Polyline] = []
        self._source_path: Path | None = None
        self._last_moves: list[Move] = []
        self._last_workpiece: tuple[float, float] | None = None

        self.params = _Parameters()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(Qt.GlobalColor.white)
        self.view.scale(1.0, -1.0)

        self.status_label = QLabel("Откройте изображение или вектор для начала.")
        self.bounds_label = QLabel("")
        self.bounds_label.setStyleSheet("color: #b04040;")
        self.time_label = QLabel("")
        self.scrub_label = QLabel("Просмотр траектории:")
        self.scrub_slider = QSlider(Qt.Orientation.Horizontal)
        self.scrub_slider.setRange(0, 0)
        self.scrub_slider.setEnabled(False)
        self.scrub_slider.valueChanged.connect(self._on_scrub)
        scrub_row = QHBoxLayout()
        scrub_row.addWidget(self.scrub_label)
        scrub_row.addWidget(self.scrub_slider, stretch=1)

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
        right_layout.addLayout(scrub_row)
        right_layout.addWidget(self.preview_button)
        right_layout.addWidget(self.generate_button)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.time_label)
        right_layout.addWidget(self.bounds_label)

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

        presets_menu = self.menuBar().addMenu("&Пресеты")

        cliche_action = QAction("Клише для &тиснения (растровая, фон + зеркало)", self)
        cliche_action.triggered.connect(self._apply_cliche_preset)
        presets_menu.addAction(cliche_action)

        engrave_action = QAction("&Гравировка по линии (растровая, без зеркала)", self)
        engrave_action.triggered.connect(self._apply_engrave_preset)
        presets_menu.addAction(engrave_action)

    def _apply_cliche_preset(self) -> None:
        """Configure the form for a leather-embossing cliché.

        Cuts the background of a black-and-white image and mirrors the
        result so the impression reads correctly when pressed into leather.
        """
        self.params.set_strategy(STRATEGY_RASTER)
        self.params.invert.setChecked(True)
        self.params.mirror_x.setChecked(True)
        self.status_label.setText(
            "Пресет «Клише»: растровая, инвертировано (резать фон), зеркало по X."
        )
        if self._image is not None:
            self._on_preview()

    def _apply_engrave_preset(self) -> None:
        """Configure the form for engraving an image (cut the dark lines)."""
        self.params.set_strategy(STRATEGY_RASTER)
        self.params.invert.setChecked(False)
        self.params.mirror_x.setChecked(False)
        self.status_label.setText("Пресет «Гравировка»: растровая, резать тёмные пиксели.")
        if self._image is not None:
            self._on_preview()

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
                rparams = self.params.to_raster_parameters()
                raster = build_raster(self._image, rparams)
                moves = build_moves(raster, rparams)
                w, h = raster.width_mm, raster.height_mm
                size_text = f"{w:.1f}×{h:.1f} мм"
            elif strategy == STRATEGY_VCARVE and self._image is not None:
                vparams = self.params.to_vcarve_parameters()
                moves = build_vcarve_moves(self._image, vparams)
                w = vparams.target_width_mm
                h = w * self._image.height / self._image.width
                size_text = f"V-carve, {w:.1f}×{h:.1f} мм"
            elif strategy == STRATEGY_PROFILE and self._polylines:
                pparams = self.params.to_profile_parameters()
                moves = build_profile_moves(self._polylines, pparams)
                w = h = None
                size_text = f"полилиний: {len(self._polylines)}"
            elif strategy == STRATEGY_POCKET and self._polylines:
                kparams = self.params.to_pocket_parameters()
                moves = build_pocket_moves(self._polylines, kparams)
                if kparams.workpiece_size_mm is not None:
                    w, h = kparams.workpiece_size_mm
                else:
                    w = h = None
                size_text = (
                    f"режим {kparams.mode}, карманов: {sum(1 for p in self._polylines if p.closed)}"
                )
            else:
                return
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return

        self._last_moves = moves
        self._last_workpiece = (w, h) if (w is not None and h is not None) else None
        self.scrub_slider.setRange(0, len(moves))
        self.scrub_slider.setEnabled(len(moves) > 0)
        self.scrub_slider.blockSignals(True)
        self.scrub_slider.setValue(len(moves))
        self.scrub_slider.blockSignals(False)

        render_toolpath(self.scene, moves, raster_width_mm=w, raster_height_mm=h)
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_label.setText(f"Сегментов траектории: {len(moves)}; {size_text}")
        self._update_metrics()

    def _on_scrub(self, value: int) -> None:
        if not self._last_moves:
            return
        subset = self._last_moves[: max(0, value)]
        if self._last_workpiece is not None:
            w, h = self._last_workpiece
            render_toolpath(self.scene, subset, raster_width_mm=w, raster_height_mm=h)
        else:
            render_toolpath(self.scene, subset)

    def _update_metrics(self) -> None:
        if not self._last_moves:
            self.time_label.setText("")
            self.bounds_label.setText("")
            return
        feed_xy = float(self.params.feed_xy.value())
        feed_z = float(self.params.feed_z.value())
        safe_z = float(self.params.safe_z.value())
        minutes = estimate_duration_minutes(self._last_moves, feed_xy=feed_xy, feed_z=feed_z)
        mm, ss = divmod(round(minutes * 60.0), 60)
        hh, mm = divmod(mm, 60)
        time_str = f"{hh}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm}:{ss:02d}"
        bbox = bounding_box(self._last_moves)
        if bbox is None:
            self.time_label.setText("")
            self.bounds_label.setText("")
            return
        self.time_label.setText(
            f"Оценка времени: {time_str}; bbox: "
            f"X[{bbox.min_x:.1f}…{bbox.max_x:.1f}] "
            f"Y[{bbox.min_y:.1f}…{bbox.max_y:.1f}] "
            f"Z[{bbox.min_z:.2f}…{bbox.max_z:.2f}]"
        )
        warnings = exceeds_bounds(bbox, safe_z=safe_z)
        self.bounds_label.setText("Внимание: " + "; ".join(warnings) if warnings else "")

    def _on_generate(self) -> None:
        strategy = self.params.current_strategy()
        try:
            if strategy == STRATEGY_RASTER:
                if self._image is None:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте изображение.")
                    return
                code = generate_gcode(self._image, self.params.to_raster_parameters())
            elif strategy == STRATEGY_VCARVE:
                if self._image is None:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте изображение.")
                    return
                code = generate_vcarve_gcode(self._image, self.params.to_vcarve_parameters())
            elif strategy == STRATEGY_PROFILE:
                if not self._polylines:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте SVG или DXF.")
                    return
                code = generate_profile_gcode(self._polylines, self.params.to_profile_parameters())
            else:
                if not self._polylines:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте SVG или DXF.")
                    return
                code = generate_pocket_gcode(self._polylines, self.params.to_pocket_parameters())
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
