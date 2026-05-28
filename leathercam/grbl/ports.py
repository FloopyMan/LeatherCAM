"""Serial port enumeration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str


def list_serial_ports() -> list[PortInfo]:
    """Return all serial ports the OS reports. Empty list on failure."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [
        PortInfo(device=p.device, description=p.description or "") for p in list_ports.comports()
    ]
