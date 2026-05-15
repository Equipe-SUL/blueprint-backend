from __future__ import annotations

import json
from typing import Any, Dict, List

from core.engine import EngineResult


def to_geojson(result: EngineResult) -> Dict[str, Any]:
    features: List[Dict[str, Any]] = []

    for i, room in enumerate(result.rooms):
        if i >= len(result.metrics.rooms):
            continue
        poly = result.polygons[i]
        rm = result.metrics.rooms[i]

        outer = [(round(v.x, 4), round(v.y, 4)) for v in poly.outer.vertices]
        ring = outer + [outer[0]]

        coords = [ring]
        for hole in poly.holes:
            h = [(round(v.x, 4), round(v.y, 4)) for v in hole.vertices]
            coords.append(h + [h[0]])

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords,
            },
            "properties": {
                "id": i,
                "nome": room.get("nome_sugerido", f"Ambiente {i + 1}"),
                "area_m2": rm.area_m2,
                "perimetro_m": rm.perimeter_m,
                "centroid_x": rm.centroid_x,
                "centroid_y": rm.centroid_y,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def to_geojson_str(result: EngineResult, indent: int = 2) -> str:
    return json.dumps(to_geojson(result), indent=indent, ensure_ascii=False)
