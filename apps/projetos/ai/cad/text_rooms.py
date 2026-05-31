from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple


# Threshold padrão em metros para pareamento texto-ambiente.
# É ajustado automaticamente pela escala do DXF quando disponível.
DEFAULT_MATCH_DISTANCE = 3.0


def detect_rooms_from_texts(
    texts: List[Dict[str, Any]],
    unit_scale: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Detecta ambientes cruzando textos TXT_AMBIENTE com TXT_ÁREA por proximidade.

    Parâmetros:
        texts      : lista de textos extraídos do DXF
        unit_scale : fator de escala das unidades do DXF para metros
                     (ex: 0.01 se unidades = cm, 0.001 se mm, 1.0 se metros)
    """
    ambiente = [t for t in texts if t.get("layer") == "TXT_AMBIENTE"]
    area = [t for t in texts if t.get("layer") == "TXT_ÁREA"]

    # Calcular threshold adaptativo baseado na escala das unidades
    if unit_scale > 0 and unit_scale != 1.0:
        # Converter threshold de metros para unidades do DXF
        match_distance = DEFAULT_MATCH_DISTANCE / unit_scale
    else:
        match_distance = DEFAULT_MATCH_DISTANCE

    # Se nenhum dos dois está disponível, tentar inferir do bounding box
    if ambiente and area:
        all_positions = []
        for t in ambiente + area:
            pos = t.get("position")
            if pos:
                all_positions.append((pos["x"], pos["y"]))
        if len(all_positions) >= 2:
            xs = [p[0] for p in all_positions]
            ys = [p[1] for p in all_positions]
            bbox_diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
            # Usar 10% da diagonal do bbox como fallback se é maior que o threshold
            if bbox_diag > 0:
                inferred = bbox_diag * 0.10
                match_distance = max(match_distance, inferred)

    unmatched_ambientes = list(ambiente)
    rooms: List[Dict[str, Any]] = []

    for at in area:
        area_text = at.get("texto", "")
        m = re.search(r"([\d,]+\.?[\d]*)", area_text)
        if not m:
            continue
        area_value = float(m.group(1).replace(",", "."))
        area_pos = at.get("position")
        if not area_pos:
            continue
        ax, ay = area_pos["x"], area_pos["y"]

        best_dist = float("inf")
        best_amb = None
        best_idx = -1
        for i, amb in enumerate(unmatched_ambientes):
            pos = amb.get("position")
            if not pos:
                continue
            dx = pos["x"] - ax
            dy = pos["y"] - ay
            dist = math.hypot(dx, dy)
            if dist < best_dist:
                best_dist = dist
                best_amb = amb
                best_idx = i

        if best_amb and best_dist < match_distance:
            unmatched_ambientes.pop(best_idx)
            rooms.append({
                "nome": best_amb.get("texto", "?"),
                "area_m2": area_value,
                "centroid_x": round(best_amb["position"]["x"], 4),
                "centroid_y": round(best_amb["position"]["y"], 4),
            })

    for amb in unmatched_ambientes:
        pos = amb.get("position")
        rooms.append({
            "nome": amb.get("texto", "?"),
            "area_m2": None,
            "centroid_x": round(pos["x"], 4) if pos else 0,
            "centroid_y": round(pos["y"], 4) if pos else 0,
        })

    rooms.sort(key=lambda r: (r["centroid_y"], r["centroid_x"]))
    return rooms
