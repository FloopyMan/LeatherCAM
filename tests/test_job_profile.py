"""Tests for the profile (vector) variant of the job orchestrator."""

from __future__ import annotations

from leathercam.job import ProfileJobParameters, build_profile_moves, generate_profile_gcode
from leathercam.vector import Polyline


def _params(**overrides: object) -> ProfileJobParameters:
    defaults: dict[str, object] = {
        "tool_diameter_mm": 1.0,
        "side": "on",
        "depth_mm": 0.4,
        "step_down_mm": 0.4,
        "feed_xy": 600.0,
        "feed_z": 200.0,
        "spindle_rpm": 10000,
        "safe_z": 5.0,
    }
    defaults.update(overrides)
    return ProfileJobParameters(**defaults)  # type: ignore[arg-type]


def _square() -> Polyline:
    return Polyline(
        points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        closed=True,
    )


def test_build_profile_moves_returns_moves() -> None:
    moves = build_profile_moves([_square()], _params())
    assert moves


def test_generate_profile_gcode_contains_grbl_header_and_footer() -> None:
    code = generate_profile_gcode([_square()], _params())
    lines = code.splitlines()
    assert lines[0] == "G21"
    assert lines[-1] == "M30"


def test_empty_polyline_list_produces_no_motion() -> None:
    code = generate_profile_gcode([], _params())
    motion = [line for line in code.splitlines() if line.startswith("G1 ")]
    assert motion == []


def test_inside_side_shrinks_visible_bbox() -> None:
    code_on = generate_profile_gcode([_square()], _params(side="on"))
    code_inside = generate_profile_gcode([_square()], _params(side="inside"))
    assert code_on != code_inside


def test_profile_mirror_keeps_bbox_but_reverses_x_order() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 0.0), (10.0, 0.0)), closed=False)
    plain = generate_profile_gcode([poly], _params())
    mirrored = generate_profile_gcode([poly], _params(mirror_x=True))
    assert plain != mirrored
    assert "X3." in plain
    assert "X7." in mirrored
