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
from typing import Any

from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
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
from leathercam.preview import render_toolpath, render_toolpath_iso
from leathercam.profiles import Material, Tool, load_materials, load_tools
from leathercam.ui.machine_dialog import MachineDialog
from leathercam.ui.preview_view import PreviewView
from leathercam.vector import (
    Polyline,
    fit_polylines,
    load_dxf,
    load_svg,
    place_polylines,
    polylines_bbox,
)

logger = logging.getLogger(__name__)

STRATEGY_RASTER = "raster"
STRATEGY_PROFILE = "profile"
STRATEGY_POCKET = "pocket"
STRATEGY_VCARVE = "vcarve"

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"

MAX_RECENT_FILES = 5

VIEW_TOP = "top"
VIEW_ISO = "iso"

_DARK_STYLESHEET = """
QWidget { background-color: #2b2b2b; color: #e0e0e0; }
QGroupBox { border: 1px solid #444; margin-top: 8px; padding-top: 12px; }
QGroupBox::title { color: #d0d0d0; subcontrol-origin: margin; left: 8px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #3a3a3a; color: #f0f0f0;
    border: 1px solid #555; padding: 2px; }
QPushButton { background-color: #444; color: #f0f0f0; border: 1px solid #666; padding: 4px 12px; }
QPushButton:hover { background-color: #555; }
QPushButton:disabled { color: #777; }
QMenuBar { background-color: #2b2b2b; color: #e0e0e0; }
QMenu { background-color: #2b2b2b; color: #e0e0e0; }
QMenu::item:selected { background-color: #444; }
QStatusBar { background-color: #1f1f1f; color: #cccccc; }
QGraphicsView { background-color: #1a1a1a; border: 1px solid #444; }
QSlider::groove:horizontal { background: #444; height: 6px; }
QSlider::handle:horizontal { background: #888; width: 12px; margin: -4px 0; border-radius: 6px; }
"""

_LIGHT_STYLESHEET = ""  # rely on system light defaults


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
        self.vector_w = self._double(0.1, 500.0, 50.0, 0.5, " мм")
        self.vector_h = self._double(0.1, 500.0, 30.0, 0.5, " мм")
        self.vector_keep_aspect = QCheckBox("Сохранять пропорции")
        self.vector_keep_aspect.setChecked(True)
        self.vector_w.valueChanged.connect(self._on_vector_width_changed)
        self.vector_h.valueChanged.connect(self._on_vector_height_changed)
        self._vector_aspect: float | None = None
        self._orig_vector_w: float | None = None
        self._orig_vector_h: float | None = None
        self._suppress_size_signal = False
        self.reset_vector_size_button = QPushButton("Сбросить к исходному")
        self.reset_vector_size_button.clicked.connect(self._on_reset_vector_size)
        self.reset_vector_size_button.setEnabled(False)
        self.vector_x = self._double(-500.0, 500.0, 0.0, 0.5, " мм")
        self.vector_y = self._double(-500.0, 500.0, 0.0, 0.5, " мм")
        self.center_button = QPushButton("Центрировать в заготовке")
        # MainWindow wires this up — _Parameters has no knowledge of the
        # current polylines / workpiece size.
        vector_form.addRow("Диаметр фрезы:", self.tool_diameter)
        vector_form.addRow("Сторона (Profile):", self.side)
        vector_form.addRow("Шаг (step-over, Pocket):", self.step_over)
        vector_form.addRow("Режим (Pocket):", self.pocket_mode)
        vector_form.addRow("Размер клише, ширина:", self.workpiece_w)
        vector_form.addRow("Размер клише, высота:", self.workpiece_h)
        vector_form.addRow("Размер рисунка, ширина:", self.vector_w)
        vector_form.addRow("Размер рисунка, высота:", self.vector_h)
        vector_form.addRow(self.vector_keep_aspect)
        vector_form.addRow(self.reset_vector_size_button)
        vector_form.addRow("Положение рисунка X:", self.vector_x)
        vector_form.addRow("Положение рисунка Y:", self.vector_y)
        vector_form.addRow(self.center_button)

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

    def set_original_vector_size(self, width_mm: float, height_mm: float) -> None:
        """Called after loading a vector file — pre-fills the size fields."""
        if width_mm <= 0 or height_mm <= 0:
            return
        self._orig_vector_w = width_mm
        self._orig_vector_h = height_mm
        self._vector_aspect = width_mm / height_mm
        self._suppress_size_signal = True
        self.vector_w.setValue(width_mm)
        self.vector_h.setValue(height_mm)
        self._suppress_size_signal = False
        self.reset_vector_size_button.setEnabled(True)

    def clear_original_vector_size(self) -> None:
        self._orig_vector_w = None
        self._orig_vector_h = None
        self._vector_aspect = None
        self.reset_vector_size_button.setEnabled(False)

    def _on_vector_width_changed(self, value: float) -> None:
        if self._suppress_size_signal or not self.vector_keep_aspect.isChecked():
            return
        if self._vector_aspect is None or self._vector_aspect <= 0:
            return
        self._suppress_size_signal = True
        self.vector_h.setValue(value / self._vector_aspect)
        self._suppress_size_signal = False

    def _on_vector_height_changed(self, value: float) -> None:
        if self._suppress_size_signal or not self.vector_keep_aspect.isChecked():
            return
        if self._vector_aspect is None or self._vector_aspect <= 0:
            return
        self._suppress_size_signal = True
        self.vector_w.setValue(value * self._vector_aspect)
        self._suppress_size_signal = False

    def _on_reset_vector_size(self) -> None:
        if self._orig_vector_w is None or self._orig_vector_h is None:
            return
        self.set_original_vector_size(self._orig_vector_w, self._orig_vector_h)

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
        self.view = PreviewView(self.scene, self)
        self.view.setBackgroundBrush(Qt.GlobalColor.white)
        self.view.scale(1.0, -1.0)

        self._view_mode = VIEW_TOP
        self.view_top_radio = QRadioButton("2D сверху")
        self.view_iso_radio = QRadioButton("Изометрия")
        self.view_top_radio.setChecked(True)
        view_group = QButtonGroup(self)
        view_group.addButton(self.view_top_radio)
        view_group.addButton(self.view_iso_radio)
        self.view_top_radio.toggled.connect(self._on_view_mode_changed)
        self.view_iso_radio.toggled.connect(self._on_view_mode_changed)
        self.reset_zoom_button = QPushButton("Сбросить зум")
        self.reset_zoom_button.clicked.connect(self.view.reset_zoom)
        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Вид:"))
        view_row.addWidget(self.view_top_radio)
        view_row.addWidget(self.view_iso_radio)
        view_row.addStretch(1)
        view_row.addWidget(self.reset_zoom_button)

        self.status_label = QLabel(
            "Откройте изображение или вектор для начала. "
            "Колесо мыши — зум, средняя кнопка (или Shift+ЛКМ) — панорамирование, "
            "двойной клик — вписать в окно."
        )
        self.status_label.setWordWrap(True)
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
        right_layout.addLayout(view_row)
        right_layout.addWidget(self.view, stretch=1)
        right_layout.addLayout(scrub_row)
        right_layout.addWidget(self.preview_button)
        right_layout.addWidget(self.generate_button)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.time_label)
        right_layout.addWidget(self.bounds_label)

        params_scroll = QScrollArea()
        params_scroll.setWidget(self.params)
        params_scroll.setWidgetResizable(True)
        params_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        params_scroll.setMinimumWidth(self.params.sizeHint().width() + 24)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(params_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 900])
        self.setCentralWidget(splitter)

        self._recent_menu: Any = None
        self.setAcceptDrops(True)
        self._build_menu()
        self.setStatusBar(QStatusBar(self))
        self._apply_saved_theme()
        self._refresh_recent_menu()
        self.params.center_button.clicked.connect(self._on_center_vector)

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

        self._recent_menu = file_menu.addMenu("&Недавние файлы")

        file_menu.addSeparator()

        save_action = QAction("&Сохранить G-code…", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_generate)
        file_menu.addAction(save_action)

        send_action = QAction("&Отправить на станок…", self)
        send_action.setShortcut("Ctrl+Shift+S")
        send_action.triggered.connect(self._on_send_to_machine)
        file_menu.addAction(send_action)

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

        view_menu = self.menuBar().addMenu("&Вид")
        theme_menu = view_menu.addMenu("&Тема")
        for label, key in (
            ("Светлая", THEME_LIGHT),
            ("Тёмная", THEME_DARK),
            ("Системная", THEME_SYSTEM),
        ):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, k=key: self._apply_theme(k))
            theme_menu.addAction(action)

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

    _IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")
    _VECTOR_EXTS = (".svg", ".dxf")

    def _on_open_image(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp);;Все файлы (*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _on_open_vector(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть вектор",
            "",
            "Вектор (*.svg *.dxf);;SVG (*.svg);;DXF (*.dxf);;Все файлы (*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _open_path(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix in self._IMAGE_EXTS:
            return self._load_image(path)
        if suffix in self._VECTOR_EXTS:
            return self._load_vector(path)
        QMessageBox.warning(self, "Неизвестный формат", f"Расширение {suffix!r} не поддержано")
        return False

    def _load_image(self, path: Path) -> bool:
        try:
            image = Image.open(path)
            image.load()
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {exc}")
            return False
        self._image = image
        self._polylines = []
        self._source_path = path
        self.params.set_strategy(STRATEGY_RASTER)
        self.status_label.setText(f"Загружено: {path.name} ({image.width}×{image.height} px)")
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._on_preview()
        self._remember_recent(path)
        return True

    def _load_vector(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        try:
            if suffix == ".svg":
                polylines = load_svg(path)
            elif suffix == ".dxf":
                polylines = load_dxf(path)
            else:
                return False
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать вектор: {exc}")
            return False
        if not polylines:
            QMessageBox.warning(self, "Пусто", "В файле не нашлось геометрии.")
            return False
        self._image = None
        self._polylines = polylines
        self._source_path = path
        bbox = polylines_bbox(polylines)
        if bbox is not None:
            self.params.set_original_vector_size(bbox[2] - bbox[0], bbox[3] - bbox[1])
        self.params.set_strategy(STRATEGY_PROFILE)
        self.status_label.setText(f"Загружено: {path.name} ({len(polylines)} полилиний)")
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self._on_preview()
        self._remember_recent(path)
        return True

    def _scaled_polylines(self) -> list[Polyline]:
        """Apply the form's vector-size and position settings to self._polylines.

        Pipeline: fit → place bbox.min at (0, 0) → translate by (vector_x,
        vector_y). The two-step placement lets the user think in absolute
        machine coordinates regardless of where the source file put its
        origin.
        """
        if not self._polylines:
            return []
        target_w = float(self.params.vector_w.value())
        target_h = float(self.params.vector_h.value())
        keep_aspect = bool(self.params.vector_keep_aspect.isChecked())
        try:
            scaled = fit_polylines(
                self._polylines,
                target_width_mm=target_w,
                target_height_mm=target_h,
                keep_aspect=keep_aspect,
            )
        except ValueError:
            scaled = list(self._polylines)
        dx = float(self.params.vector_x.value())
        dy = float(self.params.vector_y.value())
        return place_polylines(scaled, dx, dy)

    def _on_center_vector(self) -> None:
        """Position the scaled design at the centre of the workpiece rectangle."""
        if not self._polylines:
            return
        target_w = float(self.params.vector_w.value())
        target_h = float(self.params.vector_h.value())
        keep_aspect = bool(self.params.vector_keep_aspect.isChecked())
        try:
            scaled = fit_polylines(
                self._polylines,
                target_width_mm=target_w,
                target_height_mm=target_h,
                keep_aspect=keep_aspect,
            )
        except ValueError:
            scaled = list(self._polylines)
        bbox = polylines_bbox(scaled)
        if bbox is None:
            return
        design_w = bbox[2] - bbox[0]
        design_h = bbox[3] - bbox[1]
        workpiece_w = float(self.params.workpiece_w.value())
        workpiece_h = float(self.params.workpiece_h.value())
        cx = (workpiece_w - design_w) / 2.0
        cy = (workpiece_h - design_h) / 2.0
        self.params.vector_x.setValue(cx)
        self.params.vector_y.setValue(cy)
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
                polys = self._scaled_polylines()
                moves = build_profile_moves(polys, pparams)
                bbox = polylines_bbox(polys)
                if bbox is not None:
                    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    size_text = f"полилиний: {len(polys)}; {w:.1f}×{h:.1f} мм"
                else:
                    w = h = None
                    size_text = f"полилиний: {len(polys)}"
            elif strategy == STRATEGY_POCKET and self._polylines:
                kparams = self.params.to_pocket_parameters()
                polys = self._scaled_polylines()
                moves = build_pocket_moves(polys, kparams)
                if kparams.workpiece_size_mm is not None:
                    w, h = kparams.workpiece_size_mm
                else:
                    w = h = None
                size_text = f"режим {kparams.mode}, карманов: {sum(1 for p in polys if p.closed)}"
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

        self._render_scene(moves, w, h)
        self.view.fit_scene()
        self.status_label.setText(f"Сегментов траектории: {len(moves)}; {size_text}")
        self._update_metrics()

    def _render_scene(self, moves, w: float | None, h: float | None) -> None:
        """Dispatch to the active renderer (2-D top-down or isometric)."""
        if self._view_mode == VIEW_ISO:
            depth = None
            if self._last_moves:
                zs = [m.z for m in self._last_moves]
                deepest = min(zs)
                if deepest < 0:
                    depth = -deepest
            render_toolpath_iso(
                self.scene,
                moves,
                raster_width_mm=w,
                raster_height_mm=h,
                raster_depth_mm=depth,
            )
        else:
            render_toolpath(self.scene, moves, raster_width_mm=w, raster_height_mm=h)

    def _on_view_mode_changed(self) -> None:
        new_mode = VIEW_ISO if self.view_iso_radio.isChecked() else VIEW_TOP
        if new_mode == self._view_mode:
            return
        self._view_mode = new_mode
        # Drop the Y-flip in iso mode — iso projection handles axis
        # orientation itself, machine Z must point up on screen.
        self.view.resetTransform()
        if self._view_mode == VIEW_TOP:
            self.view.scale(1.0, -1.0)
        if not self._last_moves:
            return
        w = self._last_workpiece[0] if self._last_workpiece else None
        h = self._last_workpiece[1] if self._last_workpiece else None
        self._render_scene(self._last_moves, w, h)
        self.view.fit_scene()

    def _on_scrub(self, value: int) -> None:
        if not self._last_moves:
            return
        subset = self._last_moves[: max(0, value)]
        w = self._last_workpiece[0] if self._last_workpiece else None
        h = self._last_workpiece[1] if self._last_workpiece else None
        self._render_scene(subset, w, h)

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

    # --- Drag & drop -------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 — Qt override
        urls = event.mimeData().urls() if event.mimeData() else []
        if any(
            u.toLocalFile().lower().endswith(self._IMAGE_EXTS + self._VECTOR_EXTS) for u in urls
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 — Qt override
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file() and self._open_path(path):
                event.acceptProposedAction()
                return
        event.ignore()

    # --- Recent files ------------------------------------------------------

    def _settings(self) -> QSettings:
        return QSettings("leathercam", "leathercam")

    def _remember_recent(self, path: Path) -> None:
        settings = self._settings()
        recent = [
            str(path),
            *(p for p in settings.value("recent_files", [], list) if p != str(path)),
        ]
        recent = recent[:MAX_RECENT_FILES]
        settings.setValue("recent_files", recent)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.clear()
        recent = self._settings().value("recent_files", [], list) or []
        if not recent:
            placeholder = QAction("(пусто)", self)
            placeholder.setEnabled(False)
            self._recent_menu.addAction(placeholder)
            return
        for path_str in recent:
            path = Path(path_str)
            action = QAction(path.name, self)
            action.setToolTip(str(path))
            action.triggered.connect(lambda _checked=False, p=path: self._open_path(p))
            self._recent_menu.addAction(action)
        self._recent_menu.addSeparator()
        clear = QAction("Очистить список", self)
        clear.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(clear)

    def _clear_recent(self) -> None:
        settings = self._settings()
        settings.setValue("recent_files", [])
        self._refresh_recent_menu()

    # --- Theme -------------------------------------------------------------

    def _apply_saved_theme(self) -> None:
        saved = self._settings().value("theme", THEME_SYSTEM, str)
        self._apply_theme(saved, persist=False)

    def _apply_theme(self, theme: str, *, persist: bool = True) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        if theme == THEME_DARK:
            app.setStyleSheet(_DARK_STYLESHEET)
        elif theme == THEME_LIGHT:
            app.setStyleSheet(_LIGHT_STYLESHEET)
        else:
            app.setStyleSheet("")
        # Make sure the preview viewport background follows the theme.
        bg = self.view.palette().color(QPalette.ColorRole.Base)
        self.view.setBackgroundBrush(bg)
        if persist:
            self._settings().setValue("theme", theme)

    # --- Send to machine ---------------------------------------------------

    def _on_send_to_machine(self) -> None:
        code = self._generate_code()
        if code is None:
            return
        dialog = MachineDialog(code, parent=self)
        dialog.exec()

    def _generate_code(self) -> str | None:
        """Run the active strategy and return the G-code text (or None)."""
        strategy = self.params.current_strategy()
        try:
            if strategy == STRATEGY_RASTER:
                if self._image is None:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте изображение.")
                    return None
                return generate_gcode(self._image, self.params.to_raster_parameters())
            if strategy == STRATEGY_VCARVE:
                if self._image is None:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте изображение.")
                    return None
                return generate_vcarve_gcode(self._image, self.params.to_vcarve_parameters())
            if strategy == STRATEGY_PROFILE:
                if not self._polylines:
                    QMessageBox.information(self, "Нет данных", "Сначала откройте SVG или DXF.")
                    return None
                return generate_profile_gcode(
                    self._scaled_polylines(), self.params.to_profile_parameters()
                )
            if not self._polylines:
                QMessageBox.information(self, "Нет данных", "Сначала откройте SVG или DXF.")
                return None
            return generate_pocket_gcode(
                self._scaled_polylines(), self.params.to_pocket_parameters()
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Параметры", str(exc))
            return None

    def _on_generate(self) -> None:
        code = self._generate_code()
        if code is None:
            return
        default_name = (self._source_path.stem if self._source_path else "job") + ".gcode"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Сохранить G-code", default_name, "G-code (*.gcode *.nc *.tap);;Все файлы (*)"
        )
        if not path_str:
            return
        Path(path_str).write_text(code, encoding="utf-8")
        self.status_label.setText(f"Сохранено: {path_str}")
