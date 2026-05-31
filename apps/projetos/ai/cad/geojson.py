from __future__ import annotations

import json
from typing import Any, Dict, List

from shapely import Polygon as ShapelyPolygon


def to_geojson(rooms: list, metrics_rooms: list, polygons: list, pillars: list = None, beams: list = None) -> Dict[str, Any]:
    """
    Gera GeoJSON FeatureCollection a partir dos resultados do CAD engine.

    Usa room["index"] para indexar corretamente em polygons e metrics_rooms,
    evitando desalinhamento quando polígonos são filtrados por área mínima.
    Inclui informações enriquecidas: layers, confiança, num_vertices.
    """
    features: List[Dict[str, Any]] = []

    for room in rooms:
        idx = room.get("index", None)
        if idx is None:
            continue

        # Validar que o índice existe em ambas as listas
        if idx >= len(polygons) or idx >= len(metrics_rooms):
            continue

        poly = polygons[idx]
        rm = metrics_rooms[idx]

        outer = [(round(v.x, 4), round(v.y, 4)) for v in poly.outer.vertices]
        if len(outer) < 3:
            continue

        ring = outer + [outer[0]] if outer[0] != outer[-1] else outer

        coords = [ring]
        for hole in poly.holes:
            h = [(round(v.x, 4), round(v.y, 4)) for v in hole.vertices]
            if len(h) >= 3:
                h_ring = h + [h[0]] if h[0] != h[-1] else h
                coords.append(h_ring)

        # Validar geometria com Shapely antes de incluir
        try:
            sp = ShapelyPolygon(ring)
            if sp.is_empty or not sp.is_valid or sp.area <= 0:
                continue
        except Exception:
            continue

        properties = {
            "id": idx,
            "nome": room.get("nome_sugerido", f"Ambiente {idx + 1}"),
            "area_m2": rm.area_m2,
            "perimetro_m": rm.perimeter_m,
            "centroid_x": rm.centroid_x,
            "centroid_y": rm.centroid_y,
            "num_vertices": len(outer),
            "tem_furos": len(poly.holes) > 0,
            "type": "room",
        }

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords,
            },
            "properties": properties,
        })

    if pillars:
        for i, poly in enumerate(pillars):
            outer = [(round(v.x, 4), round(v.y, 4)) for v in poly.outer.vertices]
            if len(outer) < 3:
                continue
            ring = outer + [outer[0]] if outer[0] != outer[-1] else outer
            coords = [ring]
            for hole in poly.holes:
                h = [(round(v.x, 4), round(v.y, 4)) for v in hole.vertices]
                if len(h) >= 3:
                    h_ring = h + [h[0]] if h[0] != h[-1] else h
                    coords.append(h_ring)
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coords,
                },
                "properties": {
                    "id": f"pillar_{i}",
                    "nome": f"Pilar {i + 1}",
                    "type": "column",
                },
            })

    if beams:
        for i, seg in enumerate(beams):
            p1 = (round(seg.start.x, 4), round(seg.start.y, 4))
            p2 = (round(seg.end.x, 4), round(seg.end.y, 4))
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [p1, p2],
                },
                "properties": {
                    "id": f"beam_{i}",
                    "nome": f"Viga {i + 1}",
                    "layer": seg.layer,
                    "type": "beam",
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def to_geojson_str(rooms: list, metrics_rooms: list, polygons: list, pillars: list = None, beams: list = None, indent: int = 2) -> str:
    return json.dumps(to_geojson(rooms, metrics_rooms, polygons, pillars, beams), indent=indent, ensure_ascii=False)
