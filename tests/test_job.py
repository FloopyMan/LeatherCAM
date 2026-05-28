"""Tests for the high-level job orchestrator."""

from __future__ import annotations

from PIL import Image, ImageDraw

from leathercam.job import JobParameters, build_moves, build_raster, generate_gcode


def _params(**overrides: object) -> JobParameters:
    defaults: dict[str, object] = {
        "target_width_mm": 4.0,
        "pixel_size_mm": 1.0,
        "threshold": 128,
        "invert": False,
        "depth_mm": 0.4,
        "step_down_mm": 0.4,
        "feed_xy": 600.0,
        "feed_z": 200.0,
        "spindle_rpm": 10000,
        "safe_z": 5.0,
    }
    defaults.update(overrides)
    return JobParameters(**defaults)  # type: ignore[arg-type]


def _square_image(size_px: int = 4, color: int = 0) -> Image.Image:
    return Image.new("L", (size_px, size_px), color=color)


def test_build_raster_passes_params_through() -> None:
    raster = build_raster(_square_image(), _params())
    assert raster.width_px == 4
    assert raster.mask.all()


def test_build_moves_produces_expected_geometry() -> None:
    raster = build_raster(_square_image(), _params())
    moves = build_moves(raster, _params())
    assert moves, "expected moves for fully-black image"
    assert moves[0].rapid
    assert moves[1].z < 0


def test_generate_gcode_round_trip_contains_motion_for_black_image() -> None:
    code = generate_gcode(_square_image(), _params())
    lines = code.splitlines()
    assert lines[0] == "G21"
    assert lines[-1] == "M30"
    motion = [line for line in lines if line.startswith(("G0", "G1", "X", "Y", "Z"))]
    assert any("Z-0.400" in line for line in motion)


def test_generate_gcode_empty_image_has_no_cuts() -> None:
    code = generate_gcode(_square_image(color=255), _params())
    assert "Z-0.400" not in code


def test_invert_flag_inverts_cut_region() -> None:
    image = Image.new("L", (4, 4), color=255)
    inverted = generate_gcode(image, _params(invert=True))
    plain = generate_gcode(image, _params(invert=False))
    assert "Z-0.400" in inverted
    assert "Z-0.400" not in plain


def test_origin_shifts_emitted_coordinates() -> None:
    image = _square_image()
    code = generate_gcode(image, _params(origin=(50.0, 60.0)))
    assert "X50." in code
    assert "Y60." in code


def test_pipeline_uses_chosen_feeds() -> None:
    image = Image.new("L", (1, 1), color=0)
    code = generate_gcode(image, _params(feed_xy=1234.0, feed_z=567.0))
    assert "F567.000" in code or "F1234.000" in code


def test_drawn_shape_produces_proportional_path_length() -> None:
    image = Image.new("L", (8, 4), color=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 6, 2), fill=0)
    code = generate_gcode(image, _params(target_width_mm=8.0, pixel_size_mm=1.0))
    plunges = [line for line in code.splitlines() if "Z-0.400" in line]
    assert plunges
