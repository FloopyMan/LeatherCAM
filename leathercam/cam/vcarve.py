"""V-carve toolpath strategy via Euclidean distance transform.

For each Z level between safe and the deepest cut, the V-bit's centerline
must stay where the distance to the nearest "off" pixel (mask boundary)
is at least depth * tan(angle/2). We extract that iso-distance contour at
each level with OpenCV and convert it to a list of Moves.

The deepest level corresponds to the medial axis of the mask — exactly
where a sharp V-tip should end up in the material.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

from leathercam.gcode import Move
from leathercam.image.preprocess import Raster


def v_carve(
    raster: Raster,
    *,
    v_angle_deg: float,
    max_depth_mm: float,
    step_down_mm: float,
    safe_z: float,
    origin: tuple[float, float] = (0.0, 0.0),
) -> list[Move]:
    """Generate V-carve moves from a binary mask using level-set passes.

    v_angle_deg   — included angle of the V-bit (e.g. 60 or 90).
    max_depth_mm  — clamp depth at this value even if the local distance
                    transform would allow deeper.
    step_down_mm  — vertical spacing of the level-set passes.
    """
    if v_angle_deg <= 0 or v_angle_deg >= 180:
        raise ValueError("v_angle_deg must be in (0, 180)")
    if max_depth_mm <= 0:
        raise ValueError("max_depth_mm must be positive")
    if step_down_mm <= 0:
        raise ValueError("step_down_mm must be positive")
    if safe_z <= 0:
        raise ValueError("safe_z must be positive")

    px = raster.pixel_size_mm
    height_px, _ = raster.mask.shape
    ox, oy = origin

    distance_px = distance_transform_edt(raster.mask)
    distance_mm = np.asarray(distance_px, dtype=np.float64) * px

    half_angle = math.radians(v_angle_deg / 2.0)
    tan_half = math.tan(half_angle)

    achievable_depth = float(distance_mm.max()) / tan_half if distance_mm.size else 0.0
    deepest = min(max_depth_mm, achievable_depth)
    if deepest <= 0:
        return []

    n_passes = math.ceil(deepest / step_down_mm)
    z_levels = [min(step_down_mm * i, deepest) for i in range(1, n_passes + 1)]

    moves: list[Move] = []
    for depth in z_levels:
        required_distance_mm = depth * tan_half
        level_mask = (distance_mm >= required_distance_mm).astype(np.uint8)
        if not level_mask.any():
            continue
        contours, _ = cv2.findContours(level_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        z = -depth
        for contour in contours:
            if len(contour) < 2:
                continue
            polyline = []
            for point in contour.reshape(-1, 2):
                col, row = int(point[0]), int(point[1])
                x = ox + (col + 0.5) * px
                y = oy + (height_px - 1 - row + 0.5) * px
                polyline.append((x, y))
            if len(polyline) < 2:
                continue
            first_x, first_y = polyline[0]
            moves.append(Move(x=first_x, y=first_y, z=safe_z, rapid=True))
            moves.append(Move(x=first_x, y=first_y, z=z, rapid=False))
            for px_x, px_y in polyline[1:]:
                moves.append(Move(x=px_x, y=px_y, z=z, rapid=False))
            moves.append(Move(x=first_x, y=first_y, z=z, rapid=False))
            moves.append(Move(x=first_x, y=first_y, z=safe_z, rapid=True))
    return moves
