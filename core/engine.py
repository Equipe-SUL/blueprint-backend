from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import math

from ezdxf.math import Vec2

from core.config import config
from core.geometry.ir import GeometryIR, Segment, Polygon as PolyIR
from core.geometry.curve_resolution import flatten_curves
from core.healing.healer import heal
from core.metrics.engine import MetricResult, compute_metrics
from core.parser.dxf_parser import parse_dxf
from core.polygonization.polygonizer import polygonize_segments, PolygonizeResult
from core.polygonization.validation import validate_polygons
from core.semantic.classifier import classify_rooms
from core.topology.graph import TopologyGraph


ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class EngineResult:
    success: bool
    ir: Optional[GeometryIR] = None
    segments: List[Segment] = field(default_factory=list)
    topology: Optional[TopologyGraph] = None
    polygons: list = field(default_factory=list)
    polygonize_result: Optional[PolygonizeResult] = None
    metrics: Optional[MetricResult] = None
    rooms: List[Dict[str, Any]] = field(default_factory=list)
    texts: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)


def _polygon_area_shoelace(poly: PolyIR) -> float:
    verts = [(v.x, v.y) for v in poly.outer.vertices]
    n = len(verts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def _scale_segments(segments: List[Segment], scale: float) -> List[Segment]:
    return [Segment(start=Vec2(s.x * scale, s.y * scale),
                    end=Vec2(e.x * scale, e.y * scale))
            for s, e in [(seg.start, seg.end) for seg in segments]]


def _scale_texts(texts: list, scale: float) -> list:
    scaled = []
    for t in texts:
        pos = t.get("position")
        if pos:
            t = dict(t)
            t["position"] = {"x": pos["x"] * scale, "y": pos["y"] * scale}
        scaled.append(t)
    return scaled


def _filter_by_area(polygons: list, min_area: float) -> list:
    return [p for p in polygons if _polygon_area_shoelace(p) >= min_area]


_ADAPTIVE_SNAP: float | None = None
_ADAPTIVE_AREA: float | None = None
_ADAPTIVE_FLATTEN: float | None = None


def _compute_scale(ir: GeometryIR) -> float:
    segs = ir.segments[:1000]
    if segs:
        lengths = [s.length() for s in segs]
        lengths.sort()
        return max(lengths[len(lengths) // 2], 1e-20)
    for arc in ir.arcs[:10]:
        return max(arc.radius * 2 * math.pi / 8, 1e-20)
    for circ in ir.circles[:10]:
        return max(circ.radius * 2 * math.pi / 8, 1e-20)
    for ell in ir.ellipses[:10]:
        return max(ell.major_axis.magnitude * 2 * math.pi / 8, 1e-20)
    for spl in ir.splines[:10]:
        pts = spl.control_points
        if len(pts) >= 2:
            d = pts[0].distance(pts[-1])
            if d > 0:
                return max(d / len(pts), 1e-20)
    return 1.0


def _adaptive_params(ir: GeometryIR, reset: bool = False) -> None:
    global _ADAPTIVE_SNAP, _ADAPTIVE_AREA, _ADAPTIVE_FLATTEN
    if _ADAPTIVE_SNAP is not None and not reset:
        return

    scale = _compute_scale(ir)

    _ADAPTIVE_SNAP = min(config.snap_radius, scale * 0.1)
    _ADAPTIVE_SNAP = max(_ADAPTIVE_SNAP, 1e-20)
    _ADAPTIVE_AREA = min(config.min_area, (scale * 10) ** 2)
    _ADAPTIVE_AREA = max(_ADAPTIVE_AREA, 1e-30)
    _ADAPTIVE_FLATTEN = min(config.flatten_epsilon, scale * 0.01)
    _ADAPTIVE_FLATTEN = max(_ADAPTIVE_FLATTEN, 1e-20)


def _step(cb: ProgressCallback, pct: float, msg: str) -> None:
    if cb:
        cb(pct, msg)


def process_dxf(filepath: str,
                progress_callback: ProgressCallback = None) -> EngineResult:
    result = EngineResult(success=False)

    try:
        _step(progress_callback, 0.0, "Lendo DXF")

        ir = parse_dxf(filepath)
        if not ir:
            result.error = "Nenhuma entidade geométrica encontrada no DXF"
            result.ir = ir
            return result
        result.ir = ir

        _step(progress_callback, 0.15, "Achatando curvas")

        _adaptive_params(ir)
        segments = flatten_curves(ir, _ADAPTIVE_FLATTEN)
        if not segments:
            result.error = "Nenhum segmento após flattening de curvas"
            result.ir = ir
            return result
        if ir.unit_scale != 1.0:
            segments = _scale_segments(segments, ir.unit_scale)
            ir.texts = _scale_texts(ir.texts, ir.unit_scale)
        result.segments = segments

        _step(progress_callback, 0.30, f"Aplicando healing ({len(segments)} segmentos)")

        _adaptive_params(ir, reset=True)
        healed = heal(segments, snap_radius=_ADAPTIVE_SNAP, epsilon=_ADAPTIVE_SNAP)
        if not healed:
            result.error = "Nenhum segmento após healing"
            return result

        use_graph = not config.skip_graph and len(healed) < config.batch_size

        if use_graph:
            _step(progress_callback, 0.45, "Construindo grafo de topologia")
            topology = TopologyGraph.from_segments(healed)
            result.topology = topology

        _step(progress_callback, 0.55, "Detectando polígonos")

        poly_result = polygonize_segments(healed)
        result.polygonize_result = poly_result
        if not poly_result.polygons:
            result.error = "Nenhum polígono encontrado"
            return result

        _step(progress_callback, 0.70, "Validando polígonos")

        polygons = validate_polygons(poly_result.polygons)
        if not polygons:
            result.error = "Nenhum polígono válido após validação"
            return result
        result.polygons = polygons

        rooms_polygons = _filter_by_area(polygons, _ADAPTIVE_AREA)
        if not rooms_polygons:
            result.polygons = polygons
        else:
            result.polygons = rooms_polygons

        _step(progress_callback, 0.80, "Calculando métricas")

        metrics = compute_metrics(result.polygons)
        result.metrics = metrics

        _step(progress_callback, 0.90, "Classificando ambientes")

        result.texts = ir.texts
        result.rooms = classify_rooms(result.polygons, ir.texts)

        _step(progress_callback, 1.0, "Finalizado")

        result.success = True
        result.stats = {
            "entidades_dxf": len(ir.segments) + len(ir.arcs) + len(ir.circles),
            "segmentos_brutos": len(segments),
            "segmentos_healed": len(healed),
            "vertices_grafo": topology.node_count() if use_graph else -1,
            "arestas_grafo": topology.edge_count() if use_graph else -1,
            "poligonos": len(polygons),
            "ambientes": len(metrics.rooms),
            "area_total_m2": metrics.total_area,
            "perimetro_total_m": metrics.total_perimeter,
            "dangles": poly_result.dangles,
            "cuts": poly_result.cuts,
            "invalid_rings": poly_result.invalid_rings,
        }

    except Exception as e:
        result.error = str(e)

    return result
