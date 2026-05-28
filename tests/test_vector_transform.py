"""Tests for vector transforms."""

from __future__ import annotations

import pytest

from leathercam.vector import Polyline, mirror_x


def test_mirror_empty_input() -> None:
    assert mirror_x([]) == []


def test_mirror_horizontal_line_keeps_bbox() -> None:
    poly = Polyline(points=((0.0, 5.0), (10.0, 5.0)))
    flipped = mirror_x([poly])[0]
    xs = [p[0] for p in flipped.points]
    assert min(xs) == pytest.approx(0.0)
    assert max(xs) == pytest.approx(10.0)


def test_mirror_reverses_x_order() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 0.0), (10.0, 5.0)))
    flipped = mirror_x([poly])[0]
    assert flipped.points[0][0] == pytest.approx(10.0)
    assert flipped.points[1][0] == pytest.approx(7.0)
    assert flipped.points[2][0] == pytest.approx(0.0)


def test_mirror_preserves_y_coordinates() -> None:
    poly = Polyline(points=((0.0, 2.0), (10.0, 8.0)))
    flipped = mirror_x([poly])[0]
    assert flipped.points[0][1] == pytest.approx(2.0)
    assert flipped.points[1][1] == pytest.approx(8.0)


def test_mirror_preserves_closed_flag() -> None:
    poly = Polyline(points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)), closed=True)
    flipped = mirror_x([poly])[0]
    assert flipped.closed is True


def test_mirror_is_involution() -> None:
    poly = Polyline(points=((0.0, 0.0), (3.0, 4.0), (10.0, 2.0)))
    twice = mirror_x(mirror_x([poly]))[0]
    for original, restored in zip(poly.points, twice.points, strict=True):
        assert original[0] == pytest.approx(restored[0])
        assert original[1] == pytest.approx(restored[1])


def test_mirror_uses_combined_bbox_across_multiple_polylines() -> None:
    a = Polyline(points=((0.0, 0.0), (4.0, 0.0)))
    b = Polyline(points=((10.0, 0.0), (20.0, 0.0)))
    [fa, fb] = mirror_x([a, b])
    fa_xs = sorted(p[0] for p in fa.points)
    fb_xs = sorted(p[0] for p in fb.points)
    assert fa_xs == [pytest.approx(16.0), pytest.approx(20.0)]
    assert fb_xs == [pytest.approx(0.0), pytest.approx(10.0)]


def test_polylines_bbox_combines_extents() -> None:
    from leathercam.vector import polylines_bbox

    a = Polyline(points=((0.0, 2.0), (5.0, 2.0)))
    b = Polyline(points=((1.0, -3.0), (3.0, 7.0)))
    assert polylines_bbox([a, b]) == (0.0, -3.0, 5.0, 7.0)


def test_polylines_bbox_empty_returns_none() -> None:
    from leathercam.vector import polylines_bbox

    assert polylines_bbox([]) is None


def test_scale_uniform() -> None:
    from leathercam.vector import scale_polylines

    poly = Polyline(points=((1.0, 2.0), (3.0, 4.0)))
    scaled = scale_polylines([poly], 2.0)[0]
    assert scaled.points == ((2.0, 4.0), (6.0, 8.0))


def test_scale_non_uniform() -> None:
    from leathercam.vector import scale_polylines

    poly = Polyline(points=((1.0, 2.0), (3.0, 4.0)))
    scaled = scale_polylines([poly], 2.0, 0.5)[0]
    assert scaled.points == ((2.0, 1.0), (6.0, 2.0))


def test_scale_rejects_non_positive() -> None:
    from leathercam.vector import scale_polylines

    poly = Polyline(points=((0.0, 0.0), (1.0, 1.0)))
    with pytest.raises(ValueError):
        scale_polylines([poly], 0.0)
    with pytest.raises(ValueError):
        scale_polylines([poly], 1.0, -1.0)


def test_fit_polylines_keeps_aspect_by_default() -> None:
    from leathercam.vector import fit_polylines, polylines_bbox

    poly = Polyline(points=((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)), closed=True)
    fitted = fit_polylines([poly], target_width_mm=50.0)
    bbox = polylines_bbox(fitted)
    assert bbox[2] - bbox[0] == pytest.approx(50.0)
    assert bbox[3] - bbox[1] == pytest.approx(25.0)  # 5 * 5 (uniform factor)


def test_fit_polylines_non_uniform_when_aspect_unlocked() -> None:
    from leathercam.vector import fit_polylines, polylines_bbox

    poly = Polyline(points=((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)), closed=True)
    fitted = fit_polylines([poly], target_width_mm=100.0, target_height_mm=30.0, keep_aspect=False)
    bbox = polylines_bbox(fitted)
    assert bbox[2] - bbox[0] == pytest.approx(100.0)
    assert bbox[3] - bbox[1] == pytest.approx(30.0)


def test_fit_polylines_empty_returns_empty() -> None:
    from leathercam.vector import fit_polylines

    assert fit_polylines([], target_width_mm=10.0) == []


def test_fit_polylines_rejects_non_positive_target() -> None:
    from leathercam.vector import fit_polylines

    poly = Polyline(points=((0.0, 0.0), (10.0, 10.0)))
    with pytest.raises(ValueError):
        fit_polylines([poly], target_width_mm=0.0)
    with pytest.raises(ValueError):
        fit_polylines([poly], target_width_mm=10.0, target_height_mm=0.0, keep_aspect=False)


def test_translate_shifts_every_point() -> None:
    from leathercam.vector import translate_polylines

    poly = Polyline(points=((0.0, 0.0), (1.0, 2.0)))
    shifted = translate_polylines([poly], 10.0, -5.0)[0]
    assert shifted.points == ((10.0, -5.0), (11.0, -3.0))


def test_translate_zero_offset_is_noop() -> None:
    from leathercam.vector import translate_polylines

    poly = Polyline(points=((1.0, 2.0), (3.0, 4.0)))
    assert translate_polylines([poly], 0.0, 0.0)[0].points == poly.points


def test_translate_preserves_closed_flag() -> None:
    from leathercam.vector import translate_polylines

    poly = Polyline(points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)), closed=True)
    shifted = translate_polylines([poly], 5.0, 5.0)[0]
    assert shifted.closed is True


def test_place_polylines_moves_bbox_corner_to_target() -> None:
    from leathercam.vector import place_polylines, polylines_bbox

    poly = Polyline(points=((10.0, 5.0), (30.0, 5.0), (30.0, 25.0), (10.0, 25.0)), closed=True)
    placed = place_polylines([poly], 0.0, 0.0)
    bbox = polylines_bbox(placed)
    assert bbox == (0.0, 0.0, 20.0, 20.0)


def test_place_polylines_arbitrary_corner() -> None:
    from leathercam.vector import place_polylines, polylines_bbox

    poly = Polyline(points=((0.0, 0.0), (10.0, 10.0)))
    placed = place_polylines([poly], 50.0, 60.0)
    bbox = polylines_bbox(placed)
    assert bbox == (50.0, 60.0, 60.0, 70.0)


def test_place_polylines_empty_returns_empty() -> None:
    from leathercam.vector import place_polylines

    assert place_polylines([], 10.0, 20.0) == []
