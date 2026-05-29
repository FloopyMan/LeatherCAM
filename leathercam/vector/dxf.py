"""DXF importer using ezdxf.

Handles LINE, ARC, CIRCLE, ELLIPSE, LWPOLYLINE, POLYLINE and SPLINE entities
by converting each to an ezdxf Path and flattening it. Coordinates are
returned in millimeters. The DXF Y axis already points up, so no flipping
is needed (unlike SVG).
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

from leathercam.vector.types import Polyline

_SUPPORTED = {
    "LINE",
    "ARC",
    "CIRCLE",
    "ELLIPSE",
    "LWPOLYLINE",
    "POLYLINE",
    "SPLINE",
}

# $INSUNITS code -> mm per unit
_UNIT_TO_MM: dict[int, float] = {
    0: 1.0,
    1: 25.4,
    2: 25.4 * 12.0,
    4: 1.0,
    5: 10.0,
    6: 1000.0,
}


def load_dxf(source: str | Path, max_segment_mm: float = 0.2) -> list[Polyline]:
    """Read a DXF file and return its geometry as polylines in millimeters."""
    if max_segment_mm <= 0:
        raise ValueError("max_segment_mm must be positive")

    doc = ezdxf.readfile(str(source))
    units = int(doc.header.get("$INSUNITS", 0))
    scale = _UNIT_TO_MM.get(units, 1.0)
    flatten_distance = max_segment_mm / scale if scale > 0 else max_segment_mm

    polylines: list[Polyline] = []
    for entity in doc.modelspace():
        if entity.dxftype() not in _SUPPORTED:
            continue
        path = ezdxf.path.make_path(entity)
        for sub in path.sub_paths() if path.has_sub_paths else [path]:
            vertices = list(sub.flattening(distance=flatten_distance))
            if len(vertices) < 2:
                continue
            pts = tuple((float(v.x) * scale, float(v.y) * scale) for v in vertices)
            polylines.append(Polyline(points=pts, closed=bool(sub.is_closed)))
    return polylines
