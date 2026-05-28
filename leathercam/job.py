"""High-level job orchestrator: image / vector + parameters → G-code.

This module is the seam between the UI layer and the core CAM pipeline.
It stays free of Qt so it can be unit-tested headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL.Image import Image

from leathercam.cam import profile, raster_zigzag
from leathercam.cam.profile import Side
from leathercam.gcode import JobConfig, Move, postprocess
from leathercam.image import Raster, to_mask
from leathercam.vector import Polyline


@dataclass(frozen=True)
class JobParameters:
    """Stage-1 raster engraving parameters."""

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


@dataclass(frozen=True)
class ProfileJobParameters:
    """Stage-2 contour (profile) toolpath parameters."""

    tool_diameter_mm: float
    side: Side

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


def build_profile_moves(polylines: list[Polyline], params: ProfileJobParameters) -> list[Move]:
    return profile(
        polylines,
        depth_mm=params.depth_mm,
        step_down_mm=params.step_down_mm,
        safe_z=params.safe_z,
        tool_diameter_mm=params.tool_diameter_mm,
        side=params.side,
        origin=params.origin,
    )


def _config(params: JobParameters | ProfileJobParameters) -> JobConfig:
    return JobConfig(
        feed_xy=params.feed_xy,
        feed_z=params.feed_z,
        spindle_rpm=params.spindle_rpm,
        safe_z=params.safe_z,
    )


def generate_gcode(image: Image, params: JobParameters) -> str:
    """Run the raster pipeline: image → mask → toolpath → G-code text."""
    raster = build_raster(image, params)
    moves = build_moves(raster, params)
    return postprocess(moves, _config(params))


def generate_profile_gcode(polylines: list[Polyline], params: ProfileJobParameters) -> str:
    """Run the profile pipeline: polylines → contour toolpath → G-code text."""
    moves = build_profile_moves(polylines, params)
    return postprocess(moves, _config(params))
