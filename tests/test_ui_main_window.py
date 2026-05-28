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
