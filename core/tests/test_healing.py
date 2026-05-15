import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ezdxf.math import Vec2
from core.geometry.ir import Segment
from core.healing.healer import heal


def test_healing():
    segs = [
        Segment(start=Vec2(0, 0), end=Vec2(1, 0)),
        Segment(start=Vec2(1, 0.005), end=Vec2(2, 0)),
        Segment(start=Vec2(0, 0), end=Vec2(1, 0)),
    ]
    healed = heal(segs, snap_radius=0.01, epsilon=0.001)
    assert len(healed) == 2
    print("  test_healing: PASS")


if __name__ == "__main__":
    test_healing()
    print("\nAll healing tests passed!")
