from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import networkx as nx
from ezdxf.math import Vec2

from core.geometry.ir import Segment


@dataclass
class TopologyGraph:
    graph: nx.Graph = field(default_factory=nx.Graph)

    @classmethod
    def from_segments(cls, segments: List[Segment]) -> TopologyGraph:
        tg = TopologyGraph()
        for seg in segments:
            u = (seg.start.x, seg.start.y)
            v = (seg.end.x, seg.end.y)
            tg.graph.add_edge(u, v)
        return tg

    def connected_components(self) -> List[List[Tuple[float, float]]]:
        return [list(comp) for comp in nx.connected_components(self.graph)]

    def find_cycles(self) -> List[List[Tuple[float, float]]]:
        try:
            cycles = nx.cycle_basis(self.graph)
            return cycles
        except nx.NetworkXNoCycle:
            return []

    def adjacency_pairs(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        return list(self.graph.edges())

    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    def edge_count(self) -> int:
        return self.graph.number_of_edges()
