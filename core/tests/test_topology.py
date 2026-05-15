import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ezdxf.math import Vec2
from core.geometry.ir import Segment
from core.topology.graph import TopologyGraph


def test_topology_graph():
    segs = [
        Segment(start=Vec2(0, 0), end=Vec2(10, 0)),
        Segment(start=Vec2(10, 0), end=Vec2(10, 10)),
    ]
    g = TopologyGraph.from_segments(segs)
    assert g.node_count() == 3
    assert g.edge_count() == 2
    print("  test_topology_graph: PASS")


if __name__ == "__main__":
    test_topology_graph()
    print("\nAll topology tests passed!")
