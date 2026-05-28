"""GRBL 1.1 G-code postprocessor.

Converts a sequence of CAM Move objects into a textual G-code program suitable
for CNC 3018 running GRBL 1.1. Output is strictly in millimeters, absolute
coordinates, XY plane.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    """A single CAM move in absolute millimeters.

    rapid=True is emitted as G0 (positioning, no feed). rapid=False is G1.
    """

    x: float
    y: float
    z: float
    rapid: bool = False


@dataclass(frozen=True)
class JobConfig:
    """Per-job machine parameters used by the postprocessor."""

    feed_xy: float
    feed_z: float
    spindle_rpm: int
    safe_z: float
    program_end: bool = True


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def postprocess(moves: Iterable[Move], config: JobConfig) -> str:
    """Emit a GRBL 1.1 G-code program from a sequence of moves.

    The header sets metric units (G21), absolute mode (G90), XY plane (G17),
    starts the spindle and retracts to safe Z. Modal G commands and the feed
    rate word are suppressed when unchanged. No-op moves (no axis change) are
    skipped. The footer retracts to safe Z, stops the spindle and parks at
    origin.
    """
    lines: list[str] = [
        "G21",
        "G90",
        "G17",
        f"M3 S{config.spindle_rpm}",
        f"G0 Z{_fmt(config.safe_z)}",
    ]

    last_x: float | None = None
    last_y: float | None = None
    last_z: float | None = config.safe_z
    last_g: str | None = "G0"
    last_feed: float | None = None

    for m in moves:
        x_changed = last_x is None or m.x != last_x
        y_changed = last_y is None or m.y != last_y
        z_changed = last_z is None or m.z != last_z

        if not (x_changed or y_changed or z_changed):
            continue

        g = "G0" if m.rapid else "G1"
        parts: list[str] = []
        if g != last_g:
            parts.append(g)
        if x_changed:
            parts.append(f"X{_fmt(m.x)}")
        if y_changed:
            parts.append(f"Y{_fmt(m.y)}")
        if z_changed:
            parts.append(f"Z{_fmt(m.z)}")

        if not m.rapid:
            plunge_only = z_changed and not x_changed and not y_changed
            feed = config.feed_z if plunge_only else config.feed_xy
            if feed != last_feed:
                parts.append(f"F{_fmt(feed)}")
                last_feed = feed

        lines.append(" ".join(parts))
        last_x, last_y, last_z = m.x, m.y, m.z
        last_g = g

    lines.append(f"G0 Z{_fmt(config.safe_z)}")
    lines.append("M5")
    if config.program_end:
        lines.append("G0 X0.000 Y0.000")
        lines.append("M30")

    return "\n".join(lines) + "\n"
