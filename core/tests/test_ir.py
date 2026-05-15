import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ezdxf.math import Vec2
from core.geometry.ir import Segment, Arc, Circle
from core.geometry.curve_resolution import flatten_arc, flatten_circle


def test_segment_length():
    s = Segment(start=Vec2(0, 0), end=Vec2(3, 4))
    assert abs(s.length() - 5.0) < 1e-10
    print("  test_segment_length: PASS")


def test_arc_flatten():
    arc = Arc(center=Vec2(0, 0), radius=1.0,
              start_angle=0.0, end_angle=math.pi, ccw=True)
    segs = flatten_arc(arc, 0.01)
    assert len(segs) >= 4
    for seg in segs:
        assert abs(seg.start.distance(Vec2(0, 0)) - 1.0) < 0.05
        assert abs(seg.end.distance(Vec2(0, 0)) - 1.0) < 0.05
    print("  test_arc_flatten: PASS")


def test_circle_flatten():
    circle = Circle(center=Vec2(0, 0), radius=1.0)
    segs = flatten_circle(circle, 0.01)
    assert len(segs) >= 4
    print("  test_circle_flatten: PASS")


if __name__ == "__main__":
    test_segment_length()
    test_arc_flatten()
    test_circle_flatten()
    print("\nAll IR tests passed!")
