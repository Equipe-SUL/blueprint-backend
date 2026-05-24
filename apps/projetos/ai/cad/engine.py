from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ezdxf.math import Vec2

from apps.projetos.ai.cad.config import get_cad_config
from apps.projetos.ai.cad.curve_resolution import flatten_curves
from apps.projetos.ai.cad.healer import heal
from apps.projetos.ai.cad.ir import GeometryIR, Segment, Polygon as PolyIR
from apps.projetos.ai.cad.metrics import MetricResult, compute_metrics
from apps.projetos.ai.cad.dxf_parser import parse_dxf
from apps.projetos.ai.cad.polygonizer import polygonize_segments, PolygonizeResult
from apps.projetos.ai.cad.validation import validate_polygons
from apps.projetos.ai.cad.classifier import classify_rooms
from apps.projetos.ai.cad.text_rooms import detect_rooms_from_texts
from apps.projetos.ai.cad.topology import TopologyGraph


ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class EngineResult:
    success: bool
    ir: Optional[GeometryIR] = None
    segments: list = field(default_factory=list)
    topology: Optional[TopologyGraph] = None
    polygons: list = field(default_factory=list)
    polygonize_result: Optional[PolygonizeResult] = None
    metrics: Optional[MetricResult] = None
    rooms: List[Dict[str, Any]] = field(default_factory=list)
    texts: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    geojson: Optional[dict] = None
    full_report: Optional[dict] = None
    used_text_fallback: bool = False
    pillars: list = field(default_factory=list)
    beams: list = field(default_factory=list)


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


def _scale_segments(segments: list, scale: float) -> list:
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


@dataclass
class AdaptiveParams:
    """Parâmetros adaptativos calculados por chamada (não globais)."""
    snap: float = 0.01
    area: float = 0.5
    flatten: float = 0.0001


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


def _compute_adaptive_params(ir: GeometryIR) -> AdaptiveParams:
    """Calcula parâmetros adaptativos baseados na escala do DXF. Sem estado global."""
    cfg = get_cad_config()
    scale = _compute_scale(ir)

    snap = min(cfg.snap_radius, scale * 0.1)
    snap = max(snap, 1e-20)
    area = min(cfg.min_area, (scale * 10) ** 2)
    area = max(area, 1e-30)
    flatten = min(cfg.flatten_epsilon, scale * 0.01)
    flatten = max(flatten, 1e-20)

    return AdaptiveParams(snap=snap, area=area, flatten=flatten)


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
            result.error = "Nenhuma entidade geometrica encontrada no DXF"
            result.ir = ir
            return result
        result.ir = ir

        _step(progress_callback, 0.15, "Achatando curvas")

        params = _compute_adaptive_params(ir)
        segments = flatten_curves(ir, params.flatten)
        if not segments:
            result.error = "Nenhum segmento apos flattening de curvas"
            return result
        if ir.unit_scale != 1.0:
            segments = _scale_segments(segments, ir.unit_scale)
            ir.texts = _scale_texts(ir.texts, ir.unit_scale)
            # Recalcular params após escala
            params = _compute_adaptive_params(ir)
        result.segments = segments

        _step(progress_callback, 0.30, f"Aplicando healing ({len(segments)} segmentos)")

        healed = heal(segments, snap_radius=params.snap, epsilon=params.snap)
        if not healed:
            result.error = "Nenhum segmento apos healing"
            return result

        def is_beam_layer(layer: str) -> bool:
            return any(s in layer.upper() for s in ("VIGA", "PROJEÇÃO", "PROJECAO"))

        def is_pillar_layer(layer: str) -> bool:
            return any(s in layer.upper() for s in ("PILAR", "ESTRUTURA"))

        arch_segs = [s for s in healed if not is_beam_layer(s.layer)]
        beam_segs = [s for s in healed if is_beam_layer(s.layer)]
        pillar_segs = [s for s in healed if is_pillar_layer(s.layer)]
        
        result.beams = beam_segs

        cfg = get_cad_config()
        use_graph = not cfg.skip_graph and len(arch_segs) < cfg.batch_size

        if use_graph:
            _step(progress_callback, 0.45, "Construindo grafo de topologia")
            topology = TopologyGraph.from_segments(arch_segs)
            result.topology = topology

        _step(progress_callback, 0.55, "Detectando poligonos")

        poly_result = polygonize_segments(arch_segs)
        result.polygonize_result = poly_result
        
        # Extrair pilares (polígonos estruturais menores)
        if pillar_segs:
            pillar_poly_result = polygonize_segments(pillar_segs)
            if pillar_poly_result.polygons:
                # Validamos e salvamos sem filtro de área mínima (pilares são pequenos)
                result.pillars = validate_polygons(pillar_poly_result.polygons)

        if not poly_result.polygons:
            result.error = "Nenhum poligono encontrado"
            return result

        _step(progress_callback, 0.70, "Validando poligonos")

        polygons = validate_polygons(poly_result.polygons)
        if not polygons:
            result.error = "Nenhum poligono valido apos validacao"
            return result
        result.polygons = polygons

        rooms_polygons = _filter_by_area(polygons, params.area)
        if not rooms_polygons:
            result.polygons = polygons
        else:
            result.polygons = rooms_polygons

        _step(progress_callback, 0.80, "Calculando metricas")

        metrics = compute_metrics(result.polygons)
        result.metrics = metrics

        _step(progress_callback, 0.90, "Classificando ambientes")

        result.texts = ir.texts
        result.rooms = classify_rooms(result.polygons, ir.texts)

        text_rooms = detect_rooms_from_texts(ir.texts, unit_scale=ir.unit_scale)
        if text_rooms and (not result.metrics or result.metrics.total_area < 0.5 * sum((r.get("area_m2") or 0) for r in text_rooms)):
            result.used_text_fallback = True
            result.rooms = [{
                "index": i,
                "nome_sugerido": r["nome"],
                "area_m2": r["area_m2"],
                "centroid_x": r["centroid_x"],
                "centroid_y": r["centroid_y"],
            } for i, r in enumerate(text_rooms)]
            if not result.metrics:
                from dataclasses import dataclass
                from apps.projetos.ai.cad.metrics import MetricResult
                result.metrics = MetricResult()

        _step(progress_callback, 1.0, "Finalizado")

        from apps.projetos.ai.cad.geojson import to_geojson
        result.geojson = to_geojson(result.rooms, result.metrics.rooms, result.polygons, result.pillars, result.beams)

        # ── Compilar relatório completo para o LLM ────────────────────────
        from collections import Counter
        blocks_by_type = Counter(b["nome"] for b in ir.blocks)
        blocks_by_layer = Counter(b["layer"] for b in ir.blocks)
        texts_by_layer = Counter(t.get("layer", "") for t in ir.texts)
        seg_count_by_layer = Counter()
        for s in ir.segments:
            pass
        line_total = len(ir.segments) + sum(len(a) for a in [ir.arcs, ir.circles])

        result.full_report = {
            "unidade": ir.unit_name,
            "escala": ir.unit_scale,
            "camadas": dict(ir.entities_by_layer),
            "blocos_por_tipo": dict(blocks_by_type.most_common()),
            "blocos_por_camada": dict(blocks_by_layer.most_common()),
            "blocos_detalhados": [
                {"nome": b["nome"], "layer": b["layer"],
                 "pos": (b["pos_x"], b["pos_y"]),
                 "rot": b["rotacao"]} for b in ir.blocks
            ],
            "dimensoes": ir.dimensions,
            "textos_por_camada": dict(texts_by_layer.most_common()),
            "total_entidades": sum(sum(v.values()) for v in ir.entities_by_layer.values()),
            "total_blocos": len(ir.blocks),
            "total_dimensoes": len(ir.dimensions),
            "total_textos": len(ir.texts),
            "total_segmentos_geometricos": line_total,
            "ambientes_extraidos": len(result.rooms),
        }

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
