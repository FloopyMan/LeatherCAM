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
