from __future__ import annotations

import math
from typing import Any, Dict, List

from shapely import Polygon as ShapelyPolygon, Point as ShapelyPoint

from apps.projetos.ai.cad.config import get_cad_config


TEXT_PRIORITY_LAYERS = ["TXT_AMBIENTE", "TXT_ÁREA", "TXT_GERAL"]


def classify_rooms(polygons: list, texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cfg = get_cad_config()

    by_layer: Dict[str, list] = {}
    for t in texts:
        layer = t.get("layer", "")
        by_layer.setdefault(layer, []).append(t)

    other = []
    for t in texts:
        layer = t.get("layer", "")
        if layer not in TEXT_PRIORITY_LAYERS:
            other.append(t)

    rooms: List[Dict[str, Any]] = []
    for i, poly in enumerate(polygons):
        sp = _to_shapely(poly)
        centroid = _polygon_centroid(poly, sp)

        name = None
        for layer in TEXT_PRIORITY_LAYERS:
            candidates = by_layer.get(layer, [])
            name = _find_best_text(centroid, sp, candidates, cfg.classifier_max_distance)
            if name:
                break

        if not name:
            name = _find_best_text(centroid, sp, other, cfg.classifier_max_distance)

        rooms.append({
            "index": i,
            "nome_sugerido": name or f"Ambiente {i + 1}",
            "centroid_x": round(centroid[0], 4),
            "centroid_y": round(centroid[1], 4),
        })
    return rooms


def _to_shapely(poly) -> ShapelyPolygon | None:
    """Converte um polígono IR para Shapely, tratando erros."""
    try:
        coords = [(v.x, v.y) for v in poly.outer.vertices]
        if len(coords) < 3:
            return None
        holes = []
        for hole in poly.holes:
            hc = [(v.x, v.y) for v in hole.vertices]
            if len(hc) >= 3:
                holes.append(hc)
        sp = ShapelyPolygon(coords, holes)
        if sp.is_empty or not sp.is_valid:
            from shapely import make_valid
            sp = make_valid(sp)
            if sp.geom_type == "MultiPolygon":
                sp = max(sp.geoms, key=lambda g: g.area)
        return sp if (not sp.is_empty and sp.area > 0) else None
    except Exception:
        return None


def _polygon_centroid(poly, sp: ShapelyPolygon | None = None) -> tuple:
    """
    Calcula o centroid real de um polígono usando Shapely.
    Fallback para média aritmética se Shapely falhar.
    """
    if sp is not None and not sp.is_empty:
        c = sp.centroid
        return (c.x, c.y)

    # Fallback: média aritmética
    xs = [v.x for v in poly.outer.vertices]
    ys = [v.y for v in poly.outer.vertices]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _find_best_text(
    centroid: tuple,
    sp: ShapelyPolygon | None,
    texts: List[Dict[str, Any]],
    max_distance: float,
) -> str | None:
    """
    Encontra o melhor texto para associar a um polígono.

    Prioridade:
      1. Texto contido dentro do polígono real (point-in-polygon) → bônus 0.3x
      2. Texto mais próximo do centroid dentro de max_distance
    """
    best_dist = float("inf")
    best_text = None

    for t in texts:
        pos = t.get("position")
        if not pos:
            continue
        tx, ty = pos["x"], pos["y"]

        # Verificação real de contenção usando Shapely (não bbox)
        contained = False
        if sp is not None and not sp.is_empty:
            try:
                contained = sp.contains(ShapelyPoint(tx, ty))
            except Exception:
                pass

        dx = tx - centroid[0]
        dy = ty - centroid[1]
        dist = math.sqrt(dx * dx + dy * dy)

        # Bônus de distância para textos contidos no polígono
        if contained:
            dist *= 0.3

        if dist < best_dist:
            best_dist = dist
            best_text = t.get("texto")

    if best_dist < max_distance:
        return best_text

    return None
