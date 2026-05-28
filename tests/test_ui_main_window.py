"""Smoke tests for the MainWindow.

These don't try to be exhaustive — they just confirm the window can be
constructed under the offscreen Qt platform and that the parameter form
maps to a JobParameters instance.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp() -> object:
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_main_window_constructs(qapp: object) -> None:
    from leathercam.ui.main_window import MainWindow

    window = MainWindow()
    assert window.windowTitle() == "LeatherCAM"
    assert not window.generate_button.isEnabled()


def test_parameters_form_round_trips(qapp: object) -> None:
    from leathercam.job import JobParameters
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    params = form.to_job_parameters()
    assert isinstance(params, JobParameters)
    assert params.target_width_mm > 0
    assert params.pixel_size_mm > 0
    assert params.spindle_rpm >= 1000


def test_strategy_toggle_swaps_panels(qapp: object) -> None:
    from leathercam.ui.main_window import STRATEGY_PROFILE, STRATEGY_RASTER, _Parameters

    form = _Parameters()
    form.set_strategy(STRATEGY_RASTER)
    assert form.image_box.isVisibleTo(form)
    assert not form.vector_box.isVisibleTo(form)
    form.set_strategy(STRATEGY_PROFILE)
    assert not form.image_box.isVisibleTo(form)
    assert form.vector_box.isVisibleTo(form)


def test_profile_parameters_round_trip(qapp: object) -> None:
    from leathercam.job import ProfileJobParameters
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    params = form.to_profile_parameters()
    assert isinstance(params, ProfileJobParameters)
    assert params.tool_diameter_mm > 0
    assert params.side in {"on", "inside", "outside"}


def test_cliche_preset_sets_invert_and_mirror(qapp: object) -> None:
    from leathercam.ui.main_window import STRATEGY_RASTER, MainWindow

    window = MainWindow()
    window._apply_cliche_preset()
    assert window.params.current_strategy() == STRATEGY_RASTER
    assert window.params.invert.isChecked()
    assert window.params.mirror_x.isChecked()


def test_engrave_preset_clears_invert_and_mirror(qapp: object) -> None:
    from leathercam.ui.main_window import STRATEGY_RASTER, MainWindow

    window = MainWindow()
    window.params.invert.setChecked(True)
    window.params.mirror_x.setChecked(True)
    window._apply_engrave_preset()
    assert window.params.current_strategy() == STRATEGY_RASTER
    assert not window.params.invert.isChecked()
    assert not window.params.mirror_x.isChecked()


def test_vcarve_parameters_round_trip(qapp: object) -> None:
    from leathercam.job import VCarveJobParameters
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    params = form.to_vcarve_parameters()
    assert isinstance(params, VCarveJobParameters)
    assert 0 < params.v_angle_deg < 180
    assert params.max_depth_mm > 0


def test_pocket_parameters_round_trip(qapp: object) -> None:
    from leathercam.job import PocketJobParameters
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    params = form.to_pocket_parameters()
    assert isinstance(params, PocketJobParameters)
    assert params.step_over_mm > 0


def test_apply_recommended_populates_machine_fields(qapp: object) -> None:
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    for i in range(form.material_combo.count()):
        if form.material_combo.itemData(i) == "linden":
            form.material_combo.setCurrentIndex(i)
            break
    for i in range(form.tool_combo.count()):
        if form.tool_combo.itemData(i) == "flat_1mm":
            form.tool_combo.setCurrentIndex(i)
            break

    form.feed_xy.setValue(1.0)
    form.feed_z.setValue(1.0)
    form.spindle_rpm.setValue(1000)
    form.step_down.setValue(0.1)
    form._on_apply_recommended()

    assert form.feed_xy.value() == 500
    assert form.feed_z.value() == 150
    assert form.spindle_rpm.value() == 10000
    assert form.step_down.value() == pytest.approx(0.3)
    assert form.tool_diameter.value() == pytest.approx(1.0)


def test_apply_recommended_sets_v_angle_for_vbit(qapp: object) -> None:
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    for i in range(form.material_combo.count()):
        if form.material_combo.itemData(i) == "linden":
            form.material_combo.setCurrentIndex(i)
            break
    for i in range(form.tool_combo.count()):
        if form.tool_combo.itemData(i) == "vbit_60":
            form.tool_combo.setCurrentIndex(i)
            break
    form.v_angle.setValue(45.0)
    form._on_apply_recommended()
    assert form.v_angle.value() == pytest.approx(60.0)


def test_open_path_image_dispatches_to_image_loader(qapp: object, tmp_path: object) -> None:
    from pathlib import Path

    from PIL import Image as PILImage

    from leathercam.ui.main_window import STRATEGY_RASTER, MainWindow

    image_path = Path(str(tmp_path)) / "test.png"
    PILImage.new("L", (32, 16), color=255).save(image_path)
    window = MainWindow()
    assert window._open_path(image_path)
    assert window._image is not None
    assert window.params.current_strategy() == STRATEGY_RASTER


def test_open_path_unknown_extension_warns_and_returns_false(
    qapp: object, tmp_path: object, monkeypatch
) -> None:
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from leathercam.ui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: QMessageBox.StandardButton.Ok)
    window = MainWindow()
    weird = Path(str(tmp_path)) / "file.xyz"
    weird.write_text("x")
    assert window._open_path(weird) is False


def test_recent_files_grows_then_clear(qapp: object, tmp_path: object) -> None:
    from pathlib import Path

    from PIL import Image as PILImage

    from leathercam.ui.main_window import MainWindow

    window = MainWindow()
    window._clear_recent()
    p = Path(str(tmp_path)) / "r.png"
    PILImage.new("L", (4, 4), color=0).save(p)
    window._open_path(p)
    recent = window._settings().value("recent_files", [], list)
    assert str(p) in recent
    window._clear_recent()
    assert not window._settings().value("recent_files", [], list)


def test_set_original_vector_size_locks_aspect_and_links_height(qapp: object) -> None:
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    form.set_original_vector_size(width_mm=100.0, height_mm=50.0)
    assert form.vector_w.value() == pytest.approx(100.0)
    assert form.vector_h.value() == pytest.approx(50.0)
    assert form.reset_vector_size_button.isEnabled()

    form.vector_w.setValue(200.0)
    assert form.vector_h.value() == pytest.approx(100.0)


def test_unlocked_aspect_changes_width_and_height_independently(qapp: object) -> None:
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    form.set_original_vector_size(width_mm=100.0, height_mm=50.0)
    form.vector_keep_aspect.setChecked(False)
    form.vector_w.setValue(60.0)
    assert form.vector_h.value() == pytest.approx(50.0)


def test_reset_vector_size_button_restores_original(qapp: object) -> None:
    from leathercam.ui.main_window import _Parameters

    form = _Parameters()
    form.set_original_vector_size(width_mm=80.0, height_mm=40.0)
    form.vector_w.setValue(160.0)
    form._on_reset_vector_size()
    assert form.vector_w.value() == pytest.approx(80.0)
    assert form.vector_h.value() == pytest.approx(40.0)


def test_vector_position_is_applied_after_scaling(qapp: object, tmp_path: object) -> None:
    from pathlib import Path

    from leathercam.ui.main_window import MainWindow
    from leathercam.vector import polylines_bbox

    svg_path = Path(str(tmp_path)) / "rect.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
        'viewBox="0 0 20 10"><rect x="0" y="0" width="20" height="10"/></svg>'
    )
    window = MainWindow()
    assert window._open_path(svg_path)
    window.params.vector_x.setValue(15.0)
    window.params.vector_y.setValue(25.0)
    placed = window._scaled_polylines()
    bbox = polylines_bbox(placed)
    assert bbox[0] == pytest.approx(15.0, abs=0.5)
    assert bbox[1] == pytest.approx(25.0, abs=0.5)


def test_center_button_centers_design_in_workpiece(qapp: object, tmp_path: object) -> None:
    from pathlib import Path

    from leathercam.ui.main_window import MainWindow
    from leathercam.vector import polylines_bbox

    svg_path = Path(str(tmp_path)) / "circle.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
        'viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"/></svg>'
    )
    window = MainWindow()
    assert window._open_path(svg_path)
    window.params.workpiece_w.setValue(100.0)
    window.params.workpiece_h.setValue(50.0)
    window._on_center_vector()
    placed = window._scaled_polylines()
    bbox = polylines_bbox(placed)
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    assert cx == pytest.approx(50.0, abs=0.5)
    assert cy == pytest.approx(25.0, abs=0.5)


def test_loading_svg_populates_vector_size_fields(qapp: object, tmp_path: object) -> None:
    from pathlib import Path

    from leathercam.ui.main_window import MainWindow

    svg_path = Path(str(tmp_path)) / "rect.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" '
        'viewBox="0 0 40 20"><rect x="5" y="5" width="30" height="10"/></svg>'
    )
    window = MainWindow()
    assert window._open_path(svg_path)
    assert window.params.vector_w.value() == pytest.approx(30.0, abs=0.5)
    assert window.params.vector_h.value() == pytest.approx(10.0, abs=0.5)
    assert window.params.reset_vector_size_button.isEnabled()


def test_saved_gcode_matches_preview_after_resize_and_position(
    qapp: object, tmp_path: object
) -> None:
    """Regression: previously _on_generate bypassed _scaled_polylines so
    the saved G-code used unscaled coordinates while the preview was
    correct. _generate_code (used by both Save and Send-to-machine)
    must honour the form's resize + position settings."""
    from pathlib import Path

    from leathercam.job import generate_pocket_gcode
    from leathercam.ui.main_window import STRATEGY_POCKET, MainWindow

    svg_path = Path(str(tmp_path)) / "circle.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
        'viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"/></svg>'
    )
    window = MainWindow()
    assert window._open_path(svg_path)
    window.params.set_strategy(STRATEGY_POCKET)
    window.params.vector_w.setValue(50.0)
    window.params.vector_x.setValue(30.0)
    window.params.vector_y.setValue(20.0)
    window.params.workpiece_w.setValue(120.0)
    window.params.workpiece_h.setValue(80.0)

    saved = window._generate_code()
    direct = generate_pocket_gcode(window._scaled_polylines(), window.params.to_pocket_parameters())
    assert saved == direct


def test_theme_switch_updates_application_stylesheet(qapp: object) -> None:
    from PySide6.QtWidgets import QApplication

    from leathercam.ui.main_window import THEME_DARK, THEME_LIGHT, MainWindow

    window = MainWindow()
    window._apply_theme(THEME_DARK)
    assert "background-color" in QApplication.instance().styleSheet()
    window._apply_theme(THEME_LIGHT)
    assert QApplication.instance().styleSheet() == ""
