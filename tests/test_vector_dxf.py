"""Tests for the DXF importer."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pytest

from leathercam.vector import Polyline, load_dxf


def _make_dxf(tmp_path: Path, build_msp, *, units: int = 4) -> Path:
    doc = ezdxf.new(setup=False)
    doc.header["$INSUNITS"] = units
    build_msp(doc.modelspace())
    out = tmp_path / "test.dxf"
    doc.saveas(out)
    return out


def test_line_yields_two_point_open_polyline(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_line((0, 0), (10, 5)))
    polys = load_dxf(dxf)
    assert len(polys) == 1
    assert polys[0].closed is False
    assert polys[0].points[0] == pytest.approx((0.0, 0.0))
    assert polys[0].points[-1] == pytest.approx((10.0, 5.0))


def test_lwpolyline_closed_flag_propagates(tmp_path: Path) -> None:
    def build(msp):
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)

    dxf = _make_dxf(tmp_path, build)
    polys = load_dxf(dxf)
    assert len(polys) == 1
    assert polys[0].closed is True


def test_circle_is_approximated_within_tolerance(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_circle((50, 50), radius=10))
    polys = load_dxf(dxf, max_segment_mm=0.05)
    assert len(polys) == 1
    poly = polys[0]
    assert poly.closed is True
    for x, y in poly.points:
        r = math.hypot(x - 50.0, y - 50.0)
        assert r == pytest.approx(10.0, abs=0.05)


def test_inch_units_are_converted_to_mm(tmp_path: Path) -> None:
    def build(msp):
        msp.add_line((0, 0), (1, 0))

    dxf = _make_dxf(tmp_path, build, units=1)
    polys = load_dxf(dxf)
    assert polys[0].points[-1][0] == pytest.approx(25.4, abs=1e-3)


def test_cm_units_are_converted_to_mm(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_line((0, 0), (1, 0)), units=5)
    polys = load_dxf(dxf)
    assert polys[0].points[-1][0] == pytest.approx(10.0, abs=1e-3)


def test_unitless_is_treated_as_mm(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_line((0, 0), (1, 0)), units=0)
    polys = load_dxf(dxf)
    assert polys[0].points[-1][0] == pytest.approx(1.0, abs=1e-6)


def test_multiple_entities_yield_multiple_polylines(tmp_path: Path) -> None:
    def build(msp):
        msp.add_line((0, 0), (1, 0))
        msp.add_lwpolyline([(2, 0), (3, 0), (3, 1)], close=True)

    dxf = _make_dxf(tmp_path, build)
    polys = load_dxf(dxf)
    assert len(polys) == 2


def test_unsupported_entities_are_skipped(tmp_path: Path) -> None:
    def build(msp):
        msp.add_line((0, 0), (1, 0))
        msp.add_text("hello")

    dxf = _make_dxf(tmp_path, build)
    polys = load_dxf(dxf)
    assert len(polys) == 1


def test_arc_segment_lies_on_circle(tmp_path: Path) -> None:
    def build(msp):
        msp.add_arc(center=(0, 0), radius=10, start_angle=0, end_angle=90)

    dxf = _make_dxf(tmp_path, build, units=4)
    polys = load_dxf(dxf, max_segment_mm=0.05)
    assert polys[0].closed is False
    for x, y in polys[0].points:
        assert math.hypot(x, y) == pytest.approx(10.0, abs=0.05)


def test_returns_polyline_instances(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_line((0, 0), (1, 0)))
    polys = load_dxf(dxf)
    assert all(isinstance(p, Polyline) for p in polys)


def test_rejects_non_positive_max_segment(tmp_path: Path) -> None:
    dxf = _make_dxf(tmp_path, lambda msp: msp.add_line((0, 0), (1, 0)))
    with pytest.raises(ValueError):
        load_dxf(dxf, max_segment_mm=0.0)
