"""High-level job orchestrator: image + parameters → G-code.

This module is the seam between the UI layer and the core CAM pipeline.
It stays free of Qt so it can be unit-tested headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL.Image import Image

from leathercam.cam import raster_zigzag
from leathercam.gcode import JobConfig, Move, postprocess
from leathercam.image import Raster, to_mask


@dataclass(frozen=True)
class JobParameters:
    """All user-facing knobs for a stage-1 raster engraving job."""

    target_width_mm: float
    pixel_size_mm: float
    threshold: int
    invert: bool

    depth_mm: float
    step_down_mm: float

    feed_xy: float
    feed_z: float
    spindle_rpm: int
    safe_z: float

    origin: tuple[float, float] = (0.0, 0.0)


def build_raster(image: Image, params: JobParameters) -> Raster:
    return to_mask(
        image,
        target_width_mm=params.target_width_mm,
        pixel_size_mm=params.pixel_size_mm,
        threshold=params.threshold,
        invert=params.invert,
    )


def build_moves(raster: Raster, params: JobParameters) -> list[Move]:
    return raster_zigzag(
        raster,
        depth_mm=params.depth_mm,
        step_down_mm=params.step_down_mm,
        safe_z=params.safe_z,
        origin=params.origin,
    )


def generate_gcode(image: Image, params: JobParameters) -> str:
    """Run the full pipeline: image → mask → toolpath → G-code text."""
    raster = build_raster(image, params)
    moves = build_moves(raster, params)
    config = JobConfig(
        feed_xy=params.feed_xy,
        feed_z=params.feed_z,
        spindle_rpm=params.spindle_rpm,
        safe_z=params.safe_z,
    )
    return postprocess(moves, config)
