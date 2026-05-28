"""JSON-backed store for tool and material profiles.

Profiles live in a per-user config directory (platformdirs):
- Linux:   ~/.config/leathercam/
- Windows: %APPDATA%\\leathercam\\

If the files don't exist on first load, the built-in defaults from
`leathercam.profiles.defaults` are written out. The user can then edit
the JSON by hand or via the UI.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from platformdirs import user_config_dir

from leathercam.profiles.defaults import DEFAULT_MATERIALS, DEFAULT_TOOLS
from leathercam.profiles.models import Material, Recommendation, Tool

_APP_NAME = "leathercam"
TOOLS_FILENAME = "tools.json"
MATERIALS_FILENAME = "materials.json"


def config_dir() -> Path:
    return Path(user_config_dir(_APP_NAME))


def tools_path() -> Path:
    return config_dir() / TOOLS_FILENAME


def materials_path() -> Path:
    return config_dir() / MATERIALS_FILENAME


def load_tools(path: Path | None = None, *, merge_defaults: bool = True) -> list[Tool]:
    """Load tools, optionally adding any built-in defaults missing by id."""
    p = path or tools_path()
    if not p.exists():
        save_tools(list(DEFAULT_TOOLS), p)
        return list(DEFAULT_TOOLS)
    data = json.loads(p.read_text(encoding="utf-8"))
    tools = [_tool_from_dict(d) for d in data]
    if merge_defaults:
        existing_ids = {t.id for t in tools}
        additions = [t for t in DEFAULT_TOOLS if t.id not in existing_ids]
        if additions:
            tools.extend(additions)
            save_tools(tools, p)
    return tools


def load_materials(path: Path | None = None, *, merge_defaults: bool = True) -> list[Material]:
    """Load materials, optionally adding any built-in defaults missing by id."""
    p = path or materials_path()
    if not p.exists():
        save_materials(list(DEFAULT_MATERIALS), p)
        return list(DEFAULT_MATERIALS)
    data = json.loads(p.read_text(encoding="utf-8"))
    materials = [_material_from_dict(d) for d in data]
    if merge_defaults:
        existing_ids = {m.id for m in materials}
        additions = [m for m in DEFAULT_MATERIALS if m.id not in existing_ids]
        if additions:
            materials.extend(additions)
            save_materials(materials, p)
    return materials


def save_tools(tools: list[Tool], path: Path | None = None) -> None:
    p = path or tools_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps([asdict(t) for t in tools], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_materials(materials: list[Material], path: Path | None = None) -> None:
    p = path or materials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps([_material_to_dict(m) for m in materials], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _tool_from_dict(d: dict) -> Tool:
    return Tool(
        id=d["id"],
        name=d["name"],
        kind=d["kind"],
        diameter_mm=float(d["diameter_mm"]),
        angle_deg=None if d.get("angle_deg") is None else float(d["angle_deg"]),
        flute_length_mm=(None if d.get("flute_length_mm") is None else float(d["flute_length_mm"])),
    )


def _material_from_dict(d: dict) -> Material:
    recs = tuple(
        Recommendation(
            tool_id=r["tool_id"],
            feed_xy=float(r["feed_xy"]),
            feed_z=float(r["feed_z"]),
            spindle_rpm=int(r["spindle_rpm"]),
            step_down_mm=float(r["step_down_mm"]),
        )
        for r in d.get("recommendations", [])
    )
    return Material(
        id=d["id"],
        name=d["name"],
        description=d.get("description", ""),
        recommendations=recs,
    )


def _material_to_dict(m: Material) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "recommendations": [asdict(r) for r in m.recommendations],
    }
