from __future__ import annotations

from typing import List

from ezdxf.math import Vec2
from shapely import Polygon as ShapelyPolygon, is_valid, make_valid, buffer

from core.geometry.ir import Ring, Polygon


def validate_polygons(polygons: List[Polygon]) -> List[Polygon]:
    valid: List[Polygon] = []
    for poly in polygons:
        validated = _validate_single(poly)
        if validated:
            valid.append(validated)
    return valid


def _polygon_to_shapely(poly: Polygon) -> ShapelyPolygon | None:
    outer_coords = [(v.x, v.y) for v in poly.outer.vertices]
    if len(outer_coords) < 3:
        return None

    holes_coords: List[List[tuple]] = []
    for hole in poly.holes:
        hc = [(v.x, v.y) for v in hole.vertices]
        if len(hc) >= 3:
            holes_coords.append(hc)

    try:
        return ShapelyPolygon(outer_coords, holes_coords)
    except Exception:
        return None


def _shapely_to_polygon(sp: ShapelyPolygon) -> Polygon:
    outer_coords = list(sp.exterior.coords)
    outer_ring = Ring(vertices=[Vec2(x, y) for x, y in outer_coords])

    holes: List[Ring] = []
    for interior in sp.interiors:
        ih = [(x, y) for x, y in interior.coords]
        if len(ih) >= 3:
            holes.append(Ring(vertices=[Vec2(x, y) for x, y in ih]))

    return Polygon(outer=outer_ring, holes=holes)


def _repair_polygon(sp: ShapelyPolygon) -> ShapelyPolygon | None:
    if not is_valid(sp):
        try:
            sp = make_valid(sp)
        except Exception:
            sp = buffer(sp, 0.0)

    if sp.geom_type == "MultiPolygon":
        areas = [(p.area, p) for p in sp.geoms]
        if not areas:
            return None
        sp = max(areas, key=lambda x: x[0])[1]

    if sp.is_empty or sp.area <= 0:
        return None

    return sp


def _validate_single(poly: Polygon) -> Polygon | None:
    sp = _polygon_to_shapely(poly)
    if sp is None:
        return None

    sp = _repair_polygon(sp)
    if sp is None:
        return None

    return _shapely_to_polygon(sp)
