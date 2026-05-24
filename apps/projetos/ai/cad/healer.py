from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ezdxf.math import Vec2

from apps.projetos.ai.cad.config import get_cad_config
from apps.projetos.ai.cad.ir import Segment


def heal(segments: List[Segment],
         epsilon: float | None = None,
         snap_radius: float | None = None) -> List[Segment]:
    cfg = get_cad_config()
    epsilon = epsilon if epsilon is not None else cfg.epsilon
    snap_radius = snap_radius if snap_radius is not None else cfg.snap_radius

    if not segments:
        return []

    snapped = _snap_vertices(segments, snap_radius)
    merged = _merge_duplicates(snapped, epsilon)
    collinear = _merge_collinear_safe(merged, snap_radius)
    return collinear


def _snap_vertices(segments: List[Segment], snap_radius: float) -> List[Segment]:
    """
    Unifica vértices próximos dentro de snap_radius.
    Usa grid-based snapping para performance e consistência.
    """
    canonical: Dict[Tuple[int, int], Vec2] = {}

    def _grid_key(p: Vec2) -> Tuple[int, int]:
        return (round(p.x / snap_radius), round(p.y / snap_radius))

    def _get_snapped(p: Vec2) -> Vec2:
        key = _grid_key(p)
        # Verificar a célula e as 8 células vizinhas
        for dk_x in (-1, 0, 1):
            for dk_y in (-1, 0, 1):
                neighbor_key = (key[0] + dk_x, key[1] + dk_y)
                if neighbor_key in canonical:
                    existing = canonical[neighbor_key]
                    if existing.distance(p) < snap_radius:
                        # Registrar também na célula principal
                        canonical[key] = existing
                        return existing
        # Nenhum vizinho encontrado, registrar como novo ponto canônico
        canonical[key] = p
        return p

    result: List[Segment] = []
    for seg in segments:
        s = _get_snapped(seg.start)
        e = _get_snapped(seg.end)
        if s.distance(e) > snap_radius:
            result.append(Segment(start=s, end=e, layer=seg.layer))

    return result


def _merge_duplicates(segments: List[Segment], epsilon: float) -> List[Segment]:
    seen: set[Tuple[float, float, float, float]] = set()
    result: List[Segment] = []

    for seg in segments:
        p1 = (round(seg.start.x / epsilon) * epsilon,
              round(seg.start.y / epsilon) * epsilon)
        p2 = (round(seg.end.x / epsilon) * epsilon,
              round(seg.end.y / epsilon) * epsilon)

        key1 = (p1[0], p1[1], p2[0], p2[1])
        key2 = (p2[0], p2[1], p1[0], p1[1])

        if key1 in seen or key2 in seen:
            continue

        seen.add(key1)
        result.append(seg)

    return result


def _merge_collinear_safe(segments: List[Segment], snap_radius: float) -> List[Segment]:
    """
    Mescla segmentos colineares sobrepostos, mas com proteções:

    1. Usa um threshold apertado (snap_radius * 0.3) para distância perpendicular,
       evitando fundir paredes paralelas próximas (ex: parede dupla de 15cm).

    2. Preserva os endpoints originais dos segmentos ao invés de recalculá-los
       por projeção (o que introduzia erro numérico e quebrava junções T).

    3. Segmentos muito curtos (< snap_radius) são descartados.
    """
    if not segments:
        return []

    # Threshold apertado para evitar fundir paredes paralelas
    perp_tolerance = snap_radius * 0.3

    groups: Dict[tuple, List[Segment]] = {}

    for seg in segments:
        dx = seg.end.x - seg.start.x
        dy = seg.end.y - seg.start.y
        length = math.hypot(dx, dy)
        if length < snap_radius:
            continue

        nx = dx / length
        ny = dy / length

        # Normalizar direção (sempre aponta para o semi-plano positivo)
        if nx < -1e-10 or (abs(nx) < 1e-10 and ny < 0):
            nx = -nx
            ny = -ny

        # Distância perpendicular do segmento à origem
        mid_x = (seg.start.x + seg.end.x) / 2
        mid_y = (seg.start.y + seg.end.y) / 2
        perp = -ny * mid_x + nx * mid_y
        perp_key = round(perp / perp_tolerance) * perp_tolerance

        dir_key = (round(nx, 8), round(ny, 8))
        key = (dir_key[0], dir_key[1], perp_key, seg.layer)

        if key not in groups:
            groups[key] = []
        groups[key].append(seg)

    result: List[Segment] = []
    for key, group_segs in groups.items():
        nx, ny = key[:2]

        # Projetar cada segmento no eixo da direção
        intervals: List[Tuple[float, float, Vec2, Vec2]] = []
        for seg in group_segs:
            proj_s = nx * seg.start.x + ny * seg.start.y
            proj_e = nx * seg.end.x + ny * seg.end.y
            if proj_s <= proj_e:
                intervals.append((proj_s, proj_e, seg.start, seg.end))
            else:
                intervals.append((proj_e, proj_s, seg.end, seg.start))

        # Ordenar por projeção de início
        intervals.sort(key=lambda x: x[0])

        # Mesclar intervalos sobrepostos, PRESERVANDO os endpoints originais
        merged: List[Tuple[float, float, Vec2, Vec2]] = [intervals[0]]
        for start_proj, end_proj, p_start, p_end in intervals[1:]:
            prev_start, prev_end, prev_p_start, prev_p_end = merged[-1]
            if start_proj <= prev_end + snap_radius:
                # Sobreposição ou adjacência — mesclar
                if end_proj > prev_end:
                    # Extender: manter o start original, usar o novo end
                    merged[-1] = (prev_start, end_proj, prev_p_start, p_end)
                # Else: completamente contido, manter o original
            else:
                merged.append((start_proj, end_proj, p_start, p_end))

        for start_proj, end_proj, p_start, p_end in merged:
            if end_proj - start_proj < snap_radius:
                continue
            # Usar os endpoints ORIGINAIS preservados (não recalculados)
            result.append(Segment(start=p_start, end=p_end, layer=group_segs[0].layer))

    return result
