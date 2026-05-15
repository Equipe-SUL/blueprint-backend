from __future__ import annotations

import math
from typing import Any, Dict, List

from core.config import config


def classify_rooms(polygons: list, texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rooms: List[Dict[str, Any]] = []
    for i, poly in enumerate(polygons):
        centroid = _polygon_centroid(poly)
        bbox = _polygon_bbox(poly)
        name = _find_best_text(centroid, bbox, texts)
        rooms.append({
            "index": i,
            "nome_sugerido": name or f"Ambiente {i + 1}",
            "centroid_x": round(centroid[0], 4),
            "centroid_y": round(centroid[1], 4),
        })
    return rooms


def _polygon_centroid(poly) -> tuple:
    xs = [v.x for v in poly.outer.vertices]
    ys = [v.y for v in poly.outer.vertices]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _polygon_bbox(poly) -> tuple:
    xs = [v.x for v in poly.outer.vertices]
    ys = [v.y for v in poly.outer.vertices]
    return (min(xs), min(ys), max(xs), max(ys))


def _find_best_text(centroid: tuple, bbox: tuple, texts: List[Dict[str, Any]]) -> str | None:
    best_dist = float("inf")
    best_text = None
    xmin, ymin, xmax, ymax = bbox

    for t in texts:
        pos = t.get("position")
        if not pos:
            continue
        tx, ty = pos["x"], pos["y"]

        contained = (xmin <= tx <= xmax and ymin <= ty <= ymax)

        dx = tx - centroid[0]
        dy = ty - centroid[1]
        dist = math.sqrt(dx * dx + dy * dy)

        if contained:
            dist *= 0.5

        if dist < best_dist:
            best_dist = dist
            best_text = t.get("texto")

    if best_dist < config.classifier_max_distance:
        return best_text
    if best_text and best_dist < config.classifier_max_distance * 2:
        return best_text
    return None
