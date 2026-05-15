import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ezdxf.math import Vec2
from core.geometry.ir import Segment
from core.polygonization.polygonizer import polygonize_segments, PolygonizeResult


def test_square_polygonization():
    segs = [
        Segment(start=Vec2(0, 0), end=Vec2(10, 0)),
        Segment(start=Vec2(10, 0), end=Vec2(10, 10)),
        Segment(start=Vec2(10, 10), end=Vec2(0, 10)),
        Segment(start=Vec2(0, 10), end=Vec2(0, 0)),
    ]
    result = polygonize_segments(segs)
    assert len(result.polygons) == 1
    print("  test_square_polygonization: PASS")


def test_triangle_polygonization():
    segs = [
        Segment(start=Vec2(0, 0), end=Vec2(5, 0)),
        Segment(start=Vec2(5, 0), end=Vec2(2.5, 5)),
        Segment(start=Vec2(2.5, 5), end=Vec2(0, 0)),
    ]
    result = polygonize_segments(segs)
    assert len(result.polygons) == 1
    print("  test_triangle_polygonization: PASS")


def test_rectangle_with_hole():
    outer = [
        Segment(start=Vec2(0, 0), end=Vec2(20, 0)),
        Segment(start=Vec2(20, 0), end=Vec2(20, 20)),
        Segment(start=Vec2(20, 20), end=Vec2(0, 20)),
        Segment(start=Vec2(0, 20), end=Vec2(0, 0)),
    ]
    hole = [
        Segment(start=Vec2(5, 5), end=Vec2(15, 5)),
        Segment(start=Vec2(15, 5), end=Vec2(15, 15)),
        Segment(start=Vec2(15, 15), end=Vec2(5, 15)),
        Segment(start=Vec2(5, 15), end=Vec2(5, 5)),
    ]
    result = polygonize_segments(outer + hole)
    assert len(result.polygons) >= 1
    print("  test_rectangle_with_hole: PASS")


if __name__ == "__main__":
    test_square_polygonization()
    test_triangle_polygonization()
    test_rectangle_with_hole()
    print("\nAll polygonization tests passed!")
