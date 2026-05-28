"""Tests for the 2-D toolpath preview rendering."""

from __future__ import annotations

import pytest

from leathercam.gcode import Move


@pytest.fixture(scope="module")
def qapp() -> object:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


def _scene(qapp: object) -> object:
    from PySide6.QtWidgets import QGraphicsScene

    return QGraphicsScene()


def test_empty_moves_yields_only_outline(qapp: object) -> None:
    from leathercam.preview import render_toolpath

    scene = _scene(qapp)
    render_toolpath(scene, [], raster_width_mm=10.0, raster_height_mm=5.0)
    assert len(scene.items()) == 1


def test_no_outline_when_dimensions_omitted(qapp: object) -> None:
    from leathercam.preview import render_toolpath

    scene = _scene(qapp)
    render_toolpath(scene, [])
    assert scene.items() == []


def test_moves_become_line_items(qapp: object) -> None:
    from leathercam.preview import render_toolpath

    scene = _scene(qapp)
    moves = [
        Move(x=0.0, y=0.0, z=5.0, rapid=True),
        Move(x=10.0, y=0.0, z=5.0, rapid=True),
        Move(x=10.0, y=0.0, z=-0.4, rapid=False),
        Move(x=20.0, y=0.0, z=-0.4, rapid=False),
    ]
    render_toolpath(scene, moves)
    line_items = scene.items()
    assert len(line_items) >= 2


def test_pure_z_move_does_not_add_line(qapp: object) -> None:
    from leathercam.preview import render_toolpath

    scene = _scene(qapp)
    moves = [
        Move(x=0.0, y=0.0, z=5.0, rapid=True),
        Move(x=0.0, y=0.0, z=-0.4, rapid=False),
    ]
    render_toolpath(scene, moves)
    assert scene.items() == []


def test_render_clears_previous_content(qapp: object) -> None:
    from leathercam.preview import render_toolpath

    scene = _scene(qapp)
    moves_a = [Move(x=0.0, y=0.0, z=5.0, rapid=True), Move(x=5.0, y=0.0, z=5.0, rapid=True)]
    render_toolpath(scene, moves_a)
    assert scene.items()
    render_toolpath(scene, [])
    assert scene.items() == []
