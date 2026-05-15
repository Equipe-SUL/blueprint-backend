from __future__ import annotations

from typing import Dict, List, Tuple

from ezdxf.math import Vec2

from core.config import config
from core.geometry.ir import Segment


def heal(segments: List[Segment],
         epsilon: float | None = None,
         snap_radius: float | None = None) -> List[Segment]:
    epsilon = epsilon if epsilon is not None else config.epsilon
    snap_radius = snap_radius if snap_radius is not None else config.snap_radius

    if not segments:
        return []

    snapped = _snap_vertices(segments, snap_radius)
    merged = _merge_duplicates(snapped, epsilon)
    return merged


def _snap_vertices(segments: List[Segment], snap_radius: float) -> List[Segment]:
    points: Dict[Tuple[float, float], Vec2] = {}

    def _get_snapped(p: Vec2) -> Vec2:
        key = (round(p.x / snap_radius) * snap_radius,
               round(p.y / snap_radius) * snap_radius)
        if key in points:
            return points[key]
        for k, v in points.items():
            if abs(k[0] - p.x) < snap_radius and abs(k[1] - p.y) < snap_radius:
                if v.distance(p) < snap_radius:
                    points[key] = v
                    return v
        points[key] = p
        return p

    result: List[Segment] = []
    for seg in segments:
        s = _get_snapped(seg.start)
        e = _get_snapped(seg.end)
        if s.distance(e) > snap_radius:
            result.append(Segment(start=s, end=e))

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
