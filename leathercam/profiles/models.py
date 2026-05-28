"""Data models for material and tool profiles.

A `Tool` describes a cutting tool (flat / V-bit / ball / engraver). A
`Material` describes a workpiece material and bundles a list of
`Recommendation`s — one per tool the user is likely to pair with that
material. The strategy panel can consult these to populate feed rates,
spindle RPM and step-down with sensible defaults.

All values are millimeters / mm-per-minute / rpm.
"""

from __future__ import annotations

from dataclasses import dataclass

ToolKind = str  # "flat" | "vbit" | "ball" | "engraver"


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    kind: ToolKind
    diameter_mm: float
    angle_deg: float | None = None
    flute_length_mm: float | None = None


@dataclass(frozen=True)
class Recommendation:
    tool_id: str
    feed_xy: float
    feed_z: float
    spindle_rpm: int
    step_down_mm: float


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    description: str = ""
    recommendations: tuple[Recommendation, ...] = ()

    def recommendation_for(self, tool_id: str) -> Recommendation | None:
        for rec in self.recommendations:
            if rec.tool_id == tool_id:
                return rec
        return None
