"""Tests for the isometric toolpath preview."""

from __future__ import annotations

import math

import pytest

from leathercam.gcode import Move


@pytest.fixture(scope="module")
def qapp() -> object:
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _scene(qapp: object) -> object:
    from PySide6.QtWidgets import QGraphicsScene

    return QGraphicsScene()


def test_origin_projects_to_origin() -> None:
    from leathercam.preview.toolpath_iso import project

    assert project((0.0, 0.0, 0.0)) == (0.0, 0.0)


def test_pure_x_moves_right_and_slightly_down() -> None:
    from leathercam.preview.toolpath_iso import project

    sx, sy = project((10.0, 0.0, 0.0))
    assert sx > 0
    assert sy < 0
    assert sx == pytest.approx(10.0 * math.cos(math.radians(30)))


def test_pure_y_moves_left_and_slightly_down() -> None:
    from leathercam.preview.toolpath_iso import project

    sx, sy = project((0.0, 10.0, 0.0))
    assert sx < 0
    assert sy < 0


def test_pure_z_moves_straight_up() -> None:
    from leathercam.preview.toolpath_iso import project

    sx, sy = project((0.0, 0.0, 5.0))
    assert sx == pytest.approx(0.0)
    assert sy == pytest.approx(5.0)


def test_equal_x_and_y_cancel_on_screen_x() -> None:
    """An equal X+Y diagonal should sit on the vertical centre line."""
    from leathercam.preview.toolpath_iso import project

    sx, _ = project((7.0, 7.0, 0.0))
    assert sx == pytest.approx(0.0)


def test_empty_moves_only_draws_workpiece(qapp: object) -> None:
    from leathercam.preview import render_toolpath_iso

    scene = _scene(qapp)
    render_toolpath_iso(scene, [], raster_width_mm=50.0, raster_height_mm=30.0)
    assert len(scene.items()) == 4  # four edges of the top rectangle


def test_full_workpiece_box_with_depth_draws_twelve_edges(qapp: object) -> None:
    from leathercam.preview import render_toolpath_iso

    scene = _scene(qapp)
    render_toolpath_iso(scene, [], raster_width_mm=50.0, raster_height_mm=30.0, raster_depth_mm=5.0)
    assert len(scene.items()) == 12


def test_moves_become_line_items(qapp: object) -> None:
    from leathercam.preview import render_toolpath_iso

    scene = _scene(qapp)
    moves = [
        Move(x=0.0, y=0.0, z=5.0, rapid=True),
        Move(x=10.0, y=0.0, z=5.0, rapid=True),
        Move(x=10.0, y=0.0, z=-0.4, rapid=False),
        Move(x=20.0, y=0.0, z=-0.4, rapid=False),
    ]
    render_toolpath_iso(scene, moves)
    assert len(scene.items()) >= 3


def test_render_clears_previous_content(qapp: object) -> None:
    from leathercam.preview import render_toolpath_iso

    scene = _scene(qapp)
    render_toolpath_iso(
        scene,
        [Move(x=0.0, y=0.0, z=5.0, rapid=True), Move(x=5.0, y=0.0, z=5.0, rapid=True)],
    )
    assert scene.items()
    render_toolpath_iso(scene, [])
    assert scene.items() == []


def test_yaw_90_rotates_x_point_to_match_y_point_at_zero_yaw() -> None:
    """Rotating the world 90° CCW maps a point on +X to where a point
    on +Y would land at zero yaw."""
    from leathercam.preview.toolpath_iso import project

    rotated = project((10.0, 0.0, 0.0), yaw_deg=90.0)
    reference = project((0.0, 10.0, 0.0))
    assert rotated[0] == pytest.approx(reference[0], abs=1e-6)
    assert rotated[1] == pytest.approx(reference[1], abs=1e-6)


def test_yaw_180_reflects_through_origin_for_z_zero_points() -> None:
    """A 180° yaw flips both X and Y axes; points at Z=0 reflect through
    the screen origin."""
    from leathercam.preview.toolpath_iso import project

    a = project((5.0, 3.0, 0.0))
    b = project((5.0, 3.0, 0.0), yaw_deg=180.0)
    assert b[0] == pytest.approx(-a[0])
    assert b[1] == pytest.approx(-a[1])


def test_pitch_zero_makes_top_down_projection() -> None:
    """At pitch=0 the projection collapses Y completely to screen X
    (no vertical contribution from XY) — effectively top-down."""
    from leathercam.preview.toolpath_iso import project

    sx, sy = project((3.0, 7.0, 0.0), yaw_deg=0.0, pitch_deg=0.0)
    assert sy == pytest.approx(0.0, abs=1e-6)
    assert sx == pytest.approx(3.0 - 7.0)


def test_pitch_90_makes_perfect_side_view() -> None:
    """At pitch=90 the X and Y axes flatten to vertical screen Y."""
    from leathercam.preview.toolpath_iso import project

    sx, _ = project((5.0, 0.0, 0.0), yaw_deg=0.0, pitch_deg=90.0)
    assert sx == pytest.approx(0.0, abs=1e-6)


def test_zero_length_segment_is_skipped(qapp: object) -> None:
    from leathercam.preview import render_toolpath_iso

    scene = _scene(qapp)
    moves = [
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
        Move(x=0.0, y=0.0, z=0.0, rapid=False),
    ]
    render_toolpath_iso(scene, moves)
    assert scene.items() == []
