"""Tests for the profiles module (data models, store, defaults)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leathercam.profiles import (
    DEFAULT_MATERIALS,
    DEFAULT_TOOLS,
    Material,
    Recommendation,
    Tool,
    load_materials,
    load_tools,
    save_materials,
    save_tools,
)


def test_default_tools_have_unique_ids() -> None:
    ids = [t.id for t in DEFAULT_TOOLS]
    assert len(ids) == len(set(ids))


def test_default_materials_have_unique_ids() -> None:
    ids = [m.id for m in DEFAULT_MATERIALS]
    assert len(ids) == len(set(ids))


def test_default_materials_reference_existing_tool_ids() -> None:
    tool_ids = {t.id for t in DEFAULT_TOOLS}
    for material in DEFAULT_MATERIALS:
        for rec in material.recommendations:
            assert rec.tool_id in tool_ids, (
                f"material {material.id!r} references unknown tool {rec.tool_id!r}"
            )


def test_recommendation_for_returns_matching_entry() -> None:
    material = next(m for m in DEFAULT_MATERIALS if m.id == "linden")
    rec = material.recommendation_for("flat_1mm")
    assert rec is not None
    assert rec.feed_xy > 0


def test_recommendation_for_unknown_tool_returns_none() -> None:
    material = next(m for m in DEFAULT_MATERIALS if m.id == "linden")
    assert material.recommendation_for("nonexistent") is None


def test_load_tools_writes_defaults_on_first_use(tmp_path: Path) -> None:
    target = tmp_path / "tools.json"
    assert not target.exists()
    tools = load_tools(target)
    assert target.exists()
    assert {t.id for t in tools} == {t.id for t in DEFAULT_TOOLS}


def test_load_materials_writes_defaults_on_first_use(tmp_path: Path) -> None:
    target = tmp_path / "materials.json"
    materials = load_materials(target)
    assert target.exists()
    assert {m.id for m in materials} == {m.id for m in DEFAULT_MATERIALS}


def test_save_then_load_tools_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "tools.json"
    tools = [
        Tool(id="custom", name="Custom flat", kind="flat", diameter_mm=1.5),
        Tool(id="vbit_45", name="V 45°", kind="vbit", diameter_mm=3.175, angle_deg=45.0),
    ]
    save_tools(tools, target)
    loaded = load_tools(target)
    assert loaded == tools


def test_save_then_load_materials_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "materials.json"
    materials = [
        Material(
            id="oak",
            name="Дуб",
            description="Test",
            recommendations=(
                Recommendation(
                    "flat_1mm", feed_xy=300, feed_z=100, spindle_rpm=10000, step_down_mm=0.2
                ),
            ),
        )
    ]
    save_materials(materials, target)
    loaded = load_materials(target)
    assert loaded == materials


def test_load_tools_from_corrupt_file_raises(tmp_path: Path) -> None:
    target = tmp_path / "tools.json"
    target.write_text("{not json}", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_tools(target)


def test_save_materials_pretty_prints_utf8(tmp_path: Path) -> None:
    target = tmp_path / "materials.json"
    save_materials(list(DEFAULT_MATERIALS), target)
    text = target.read_text(encoding="utf-8")
    assert "Липа" in text
    assert "\n" in text
