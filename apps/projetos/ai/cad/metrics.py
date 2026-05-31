from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from shapely import Polygon as ShapelyPolygon

from apps.projetos.ai.cad.ir import Polygon


# Tolerância para considerar dois polígonos como adjacentes (em unidades do DXF).
# Polígonos cuja distância é menor que este valor são considerados vizinhos.
ADJACENCY_TOLERANCE = 0.15


@dataclass
class RoomMetrics:
    area_m2: float
    perimeter_m: float
    centroid_x: float
    centroid_y: float
    is_valid: bool = True


@dataclass
class MetricResult:
    rooms: List[RoomMetrics] = field(default_factory=list)
    total_area: float = 0.0
    total_perimeter: float = 0.0
    adjacency: Dict[int, List[int]] = field(default_factory=dict)


def compute_metrics(polygons: List[Polygon]) -> MetricResult:
    result = MetricResult()

    shapely_polys: List[Tuple[int, ShapelyPolygon]] = []

    for i, poly in enumerate(polygons):
        outer_coords = [(v.x, v.y) for v in poly.outer.vertices]
        if len(outer_coords) < 3:
            # Adicionar métricas vazias para manter alinhamento de índices
            result.rooms.append(RoomMetrics(
                area_m2=0.0, perimeter_m=0.0,
                centroid_x=0.0, centroid_y=0.0, is_valid=False,
            ))
            continue

        holes_coords: List[List[tuple]] = []
        for hole in poly.holes:
            hc = [(v.x, v.y) for v in hole.vertices]
            if len(hc) >= 3:
                holes_coords.append(hc)

        sp = ShapelyPolygon(outer_coords, holes_coords)
        if sp.is_empty or not sp.is_valid:
            result.rooms.append(RoomMetrics(
                area_m2=0.0, perimeter_m=0.0,
                centroid_x=0.0, centroid_y=0.0, is_valid=False,
            ))
            continue

        centroid = sp.centroid
        room = RoomMetrics(
            area_m2=round(sp.area, 4),
            perimeter_m=round(sp.length, 4),
            centroid_x=round(centroid.x, 4),
            centroid_y=round(centroid.y, 4),
        )
        result.rooms.append(room)
        result.total_area += room.area_m2
        result.total_perimeter += room.perimeter_m
        shapely_polys.append((i, sp))

    result.total_area = round(result.total_area, 4)
    result.total_perimeter = round(result.total_perimeter, 4)

    result.adjacency = _compute_adjacency(shapely_polys)

    return result


def _compute_adjacency(
    shapely_polys: List[Tuple[int, ShapelyPolygon]],
    tolerance: float = ADJACENCY_TOLERANCE,
) -> Dict[int, List[int]]:
    """
    Calcula adjacência entre polígonos usando distância com tolerância.

    Dois ambientes são considerados adjacentes se a distância entre seus
    polígonos é menor que `tolerance`. Isso é muito mais robusto do que
    `touches()`, que falha com micro-gaps pós-healing.
    """
    adj: Dict[int, List[int]] = {}
    n = len(shapely_polys)

    for i in range(n):
        idx_i, sp_i = shapely_polys[i]
        for j in range(i + 1, n):
            idx_j, sp_j = shapely_polys[j]

            # Distância entre os polígonos — muito mais robusto que touches()
            dist = sp_i.distance(sp_j)
            if dist < tolerance:
                adj.setdefault(idx_i, []).append(idx_j)
                adj.setdefault(idx_j, []).append(idx_i)

    return adj
