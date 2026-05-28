"""Tests for the GRBL postprocessor."""

from __future__ import annotations

from leathercam.gcode import JobConfig, Move, postprocess


def _config(**overrides: object) -> JobConfig:
    defaults: dict[str, object] = {
        "feed_xy": 600.0,
        "feed_z": 200.0,
        "spindle_rpm": 10000,
        "safe_z": 5.0,
    }
    defaults.update(overrides)
    return JobConfig(**defaults)  # type: ignore[arg-type]


def _motion_lines(code: str) -> list[str]:
    """All lines after the preamble and before the footer."""
    lines = code.splitlines()
    return lines[5:-4]


def test_empty_moves_emits_only_preamble_and_footer() -> None:
    code = postprocess([], _config())
    assert code == ("G21\nG90\nG17\nM3 S10000\nG0 Z5.000\nG0 Z5.000\nM5\nG0 X0.000 Y0.000\nM30\n")


def test_single_combined_move_uses_feed_xy_when_xy_changes() -> None:
    moves = [Move(x=10.0, y=20.0, z=-0.4, rapid=False)]
    code = postprocess(moves, _config())
    assert "G1 X10.000 Y20.000 Z-0.400 F600.000" in code.splitlines()


def test_plunge_uses_feed_z_then_traverse_uses_feed_xy() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=0.0, rapid=True),
        Move(x=0.0, y=0.0, z=-0.5, rapid=False),
        Move(x=10.0, y=0.0, z=-0.5, rapid=False),
    ]
    code = postprocess(moves, _config())
    motion = _motion_lines(code)
    plunge = next(line for line in motion if "Z-0.500" in line)
    traverse = next(line for line in motion if "X10.000" in line)
    assert plunge == "G1 Z-0.500 F200.000"
    assert traverse == "X10.000 F600.000"


def test_modal_g_word_is_suppressed_when_unchanged() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=-0.5, rapid=False),
        Move(x=10.0, y=0.0, z=-0.5, rapid=False),
        Move(x=10.0, y=5.0, z=-0.5, rapid=False),
    ]
    code = postprocess(moves, _config())
    motion = _motion_lines(code)
    explicit_g1 = [line for line in motion if line.startswith("G1 ")]
    assert len(explicit_g1) == 1
    assert motion[1].startswith("X10.000")
    assert motion[2].startswith("Y5.000")


def test_feed_rate_is_only_emitted_when_changed() -> None:
    moves = [
        Move(x=0.0, y=0.0, z=-0.5, rapid=False),
        Move(x=1.0, y=0.0, z=-0.5, rapid=False),
        Move(x=2.0, y=0.0, z=-0.5, rapid=False),
    ]
    code = postprocess(moves, _config())
    assert code.count("F600.000") == 1


def test_no_op_move_is_skipped() -> None:
    moves = [
        Move(x=1.0, y=2.0, z=-0.3, rapid=False),
        Move(x=1.0, y=2.0, z=-0.3, rapid=False),
        Move(x=3.0, y=2.0, z=-0.3, rapid=False),
    ]
    code = postprocess(moves, _config())
    motion = _motion_lines(code)
    assert len(motion) == 2


def test_rapid_does_not_emit_feed() -> None:
    moves = [Move(x=10.0, y=10.0, z=-1.0, rapid=True)]
    code = postprocess(moves, _config())
    motion = _motion_lines(code)
    assert motion == ["X10.000 Y10.000 Z-1.000"]
    assert "F" not in motion[0]


def test_header_and_footer_structure() -> None:
    code = postprocess([Move(x=1.0, y=1.0, z=-0.1, rapid=False)], _config())
    lines = code.splitlines()
    assert lines[:5] == ["G21", "G90", "G17", "M3 S10000", "G0 Z5.000"]
    assert lines[-4:] == ["G0 Z5.000", "M5", "G0 X0.000 Y0.000", "M30"]


def test_program_end_can_be_disabled() -> None:
    code = postprocess([], _config(program_end=False))
    lines = code.splitlines()
    assert "M30" not in lines
    assert lines[-1] == "M5"


def test_numbers_use_three_decimal_places() -> None:
    moves = [Move(x=1.0 / 3.0, y=2.0 / 7.0, z=-0.123456, rapid=False)]
    code = postprocess(moves, _config())
    line = next(line for line in code.splitlines() if line.startswith("G1 "))
    assert "X0.333" in line
    assert "Y0.286" in line
    assert "Z-0.123" in line
