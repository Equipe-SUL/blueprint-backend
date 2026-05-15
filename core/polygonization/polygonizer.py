from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ezdxf.math import Vec2
from shapely import LineString, MultiLineString, Polygon as ShapelyPolygon
from shapely.ops import polygonize_full, linemerge, unary_union

from core.geometry.ir import Ring, Polygon, Segment


@dataclass
class PolygonizeResult:
    polygons: List[Polygon] = field(default_factory=list)
    dangles: int = 0
    cuts: int = 0
    invalid_rings: int = 0


def polygonize_segments(segments: List[Segment]) -> PolygonizeResult:
    if not segments:
        return PolygonizeResult()

    merged = _merge_and_union(segments)
    return _polygonize_lines(merged)


def _merge_and_union(segments: List[Segment]) -> MultiLineString:
    lines: List[LineString] = []
    for seg in segments:
        lines.append(LineString([
            (seg.start.x, seg.start.y),
            (seg.end.x, seg.end.y),
        ]))

    if not lines:
        return MultiLineString()

    merged = linemerge(lines)
    union = unary_union(merged)

    if isinstance(union, MultiLineString):
        return union
    if union.geom_type == "LineString":
        return MultiLineString([union])
    return MultiLineString()


def _polygonize_lines(lines: MultiLineString) -> PolygonizeResult:
    polygons_gc, cuts_gc, dangles_gc, invalid_gc = polygonize_full(lines)

    valid = [p for p in polygons_gc.geoms if p.geom_type == "Polygon"] if hasattr(polygons_gc, 'geoms') else []
    if not valid and hasattr(polygons_gc, 'geom_type') and polygons_gc.geom_type == 'Polygon':
        valid = [polygons_gc]

    return PolygonizeResult(
        polygons=_to_polygon_ir(valid),
        dangles=len(dangles_gc.geoms) if hasattr(dangles_gc, 'geoms') else 0,
        cuts=len(cuts_gc.geoms) if hasattr(cuts_gc, 'geoms') else 0,
        invalid_rings=len(invalid_gc.geoms) if hasattr(invalid_gc, 'geoms') else 0,
    )


def _to_polygon_ir(shapely_polygons: List[ShapelyPolygon]) -> List[Polygon]:
    polygons: List[Polygon] = []
    for sp in shapely_polygons:
        outer_coords = list(sp.exterior.coords)
        outer_ring = Ring(vertices=[Vec2(x, y) for x, y in outer_coords])

        holes: List[Ring] = []
        for interior in sp.interiors:
            hole_coords = list(interior.coords)
            holes.append(Ring(vertices=[Vec2(x, y) for x, y in hole_coords]))

        polygons.append(Polygon(outer=outer_ring, holes=holes))

    return polygons
