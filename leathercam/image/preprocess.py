"""Raster preprocessing: load an image and turn it into a binary mask
aligned to physical millimeter coordinates.

The mask convention: True == "cut here", False == "leave material".
Black pixels (dark) are treated as cut by default; invert=True swaps that.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Raster:
    """A binary mask with a uniform physical pixel size.

    Row 0 of `mask` corresponds to the top of the image; the toolpath
    generator is responsible for flipping Y when emitting machine coordinates.
    """

    mask: np.ndarray
    pixel_size_mm: float

    def __post_init__(self) -> None:
        if self.mask.dtype != np.bool_:
            raise TypeError("Raster.mask must be a boolean ndarray")
        if self.mask.ndim != 2:
            raise ValueError("Raster.mask must be 2-D (H, W)")
        if self.pixel_size_mm <= 0:
            raise ValueError("pixel_size_mm must be positive")

    @property
    def height_px(self) -> int:
        return int(self.mask.shape[0])

    @property
    def width_px(self) -> int:
        return int(self.mask.shape[1])

    @property
    def width_mm(self) -> float:
        return self.width_px * self.pixel_size_mm

    @property
    def height_mm(self) -> float:
        return self.height_px * self.pixel_size_mm


def load_image(path: str | Path) -> Image.Image:
    """Load an image from disk and return it as a PIL Image (mode unchanged)."""
    return Image.open(Path(path))


def to_mask(
    image: Image.Image,
    target_width_mm: float,
    pixel_size_mm: float,
    threshold: int = 128,
    invert: bool = False,
) -> Raster:
    """Resize the image to the requested physical size and binarize it.

    target_width_mm — desired physical width of the final raster.
    pixel_size_mm   — physical size of one mask pixel (effectively the
                      raster step-over for the engraving strategy).
    threshold       — grayscale cutoff (0..255). Pixels strictly below
                      become True ("cut") by default.
    invert          — swap True/False after thresholding.
    """
    if target_width_mm <= 0:
        raise ValueError("target_width_mm must be positive")
    if pixel_size_mm <= 0:
        raise ValueError("pixel_size_mm must be positive")
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be in [0, 255]")

    width_px = max(1, round(target_width_mm / pixel_size_mm))
    aspect = image.height / image.width
    height_px = max(1, round(width_px * aspect))

    resized = image.convert("L").resize((width_px, height_px), Image.Resampling.LANCZOS)
    arr = np.asarray(resized, dtype=np.uint8)
    mask = arr < threshold
    if invert:
        mask = ~mask
    return Raster(mask=mask, pixel_size_mm=pixel_size_mm)
