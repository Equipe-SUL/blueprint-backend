import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ezdxf.math import Vec2
from core.geometry.ir import Segment
from core.metrics.engine import compute_metrics
from core.polygonization.polygonizer import polygonize_segments
from core.polygonization.validation import validate_polygons


def test_square_metrics():
    segs = [
        Segment(start=Vec2(0, 0), end=Vec2(10, 0)),
        Segment(start=Vec2(10, 0), end=Vec2(10, 10)),
        Segment(start=Vec2(10, 10), end=Vec2(0, 10)),
        Segment(start=Vec2(0, 10), end=Vec2(0, 0)),
    ]
    poly_result = polygonize_segments(segs)
    polygons = validate_polygons(poly_result.polygons)
    metrics = compute_metrics(polygons)
    assert len(metrics.rooms) == 1
    assert abs(metrics.rooms[0].area_m2 - 100.0) < 0.01
    assert abs(metrics.rooms[0].perimeter_m - 40.0) < 0.01
    print("  test_square_metrics: PASS")


if __name__ == "__main__":
    test_square_metrics()
    print("\nAll metrics tests passed!")
