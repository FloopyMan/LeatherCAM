"""Tests for image preprocessing."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from leathercam.image import Raster, to_mask


def _make_image(width: int, height: int, fill: int = 255) -> Image.Image:
    return Image.new("L", (width, height), color=fill)


def test_raster_rejects_non_bool_mask() -> None:
    with pytest.raises(TypeError):
        Raster(mask=np.zeros((4, 4), dtype=np.uint8), pixel_size_mm=0.1)


def test_raster_rejects_non_2d_mask() -> None:
    with pytest.raises(ValueError):
        Raster(mask=np.zeros((4,), dtype=np.bool_), pixel_size_mm=0.1)


def test_raster_rejects_non_positive_pixel_size() -> None:
    with pytest.raises(ValueError):
        Raster(mask=np.zeros((2, 2), dtype=np.bool_), pixel_size_mm=0.0)


def test_raster_physical_dimensions() -> None:
    raster = Raster(mask=np.zeros((30, 50), dtype=np.bool_), pixel_size_mm=0.2)
    assert raster.width_px == 50
    assert raster.height_px == 30
    assert raster.width_mm == pytest.approx(10.0)
    assert raster.height_mm == pytest.approx(6.0)


def test_to_mask_resizes_to_target_width() -> None:
    image = _make_image(200, 100)
    raster = to_mask(image, target_width_mm=20.0, pixel_size_mm=0.1)
    assert raster.width_px == 200
    assert raster.height_px == 100


def test_to_mask_preserves_aspect_ratio() -> None:
    image = _make_image(400, 100)  # 4:1
    raster = to_mask(image, target_width_mm=40.0, pixel_size_mm=0.2)
    assert raster.width_px == 200
    assert raster.height_px == 50


def test_to_mask_black_pixels_become_true() -> None:
    image = Image.new("L", (4, 4), color=0)
    raster = to_mask(image, target_width_mm=4.0, pixel_size_mm=1.0)
    assert raster.mask.all()


def test_to_mask_white_pixels_become_false() -> None:
    image = Image.new("L", (4, 4), color=255)
    raster = to_mask(image, target_width_mm=4.0, pixel_size_mm=1.0)
    assert not raster.mask.any()


def test_to_mask_invert_flag_flips_result() -> None:
    image = Image.new("L", (4, 4), color=0)
    raster = to_mask(image, target_width_mm=4.0, pixel_size_mm=1.0, invert=True)
    assert not raster.mask.any()


def test_to_mask_threshold_boundary() -> None:
    image = Image.new("L", (4, 4), color=128)
    below = to_mask(image, 4.0, 1.0, threshold=129)
    at = to_mask(image, 4.0, 1.0, threshold=128)
    assert below.mask.all()
    assert not at.mask.any()


def test_to_mask_rejects_invalid_args() -> None:
    image = _make_image(10, 10)
    with pytest.raises(ValueError):
        to_mask(image, target_width_mm=0.0, pixel_size_mm=0.1)
    with pytest.raises(ValueError):
        to_mask(image, target_width_mm=10.0, pixel_size_mm=0.0)
    with pytest.raises(ValueError):
        to_mask(image, target_width_mm=10.0, pixel_size_mm=0.1, threshold=-1)
    with pytest.raises(ValueError):
        to_mask(image, target_width_mm=10.0, pixel_size_mm=0.1, threshold=256)


def test_to_mask_converts_rgb_to_grayscale() -> None:
    image = Image.new("RGB", (4, 4), color=(0, 0, 0))
    raster = to_mask(image, target_width_mm=4.0, pixel_size_mm=1.0)
    assert raster.mask.all()
