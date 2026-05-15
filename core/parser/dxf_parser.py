from __future__ import annotations

import math
from typing import List, Optional

import ezdxf
from ezdxf import recover
from ezdxf.math import Vec2, Vec3, OCS
from core.config import is_layer_allowed
from core.geometry.ir import GeometryIR, Segment, Arc, Circle, Spline, Ellipse


INSUNITS_MAP = {
    0: 1.0, 1: 0.0254, 2: 0.3048, 3: 1609.344,
    4: 0.001, 5: 0.01, 6: 1.0, 7: 0.000001, 8: 0.000000001,
    9: 0.000000000001, 10: 0.000000000000001, 11: 0.0009144,
    12: 0.000000000000000001, 13: 0.01, 14: 0.1, 15: 1000.0,
    16: 0.000000001, 17: 0.000001, 18: 0.001,
    19: 0.0254, 20: 0.3048,
}

IGNORED_ENTITIES = frozenset({
    "RAY", "XLINE", "VIEWPORT", "MESH",
    "POINT", "ATTDEF", "ATTRIB",
    "ACIS", "BODY", "REGION", "SURFACE",
    "UNDERLAY", "XREF", "LIGHT",
    "IMAGE", "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY",
    "TABLE", "TOLERANCE", "OLEFRAME", "OLE2FRAME",
    "SECTION", "SUN", "RTEXT", "ARCTEXT",
})


def parse_dxf(filepath: str) -> GeometryIR:
    ir = GeometryIR()
    doc = None

    try:
        doc = ezdxf.readfile(filepath)
    except Exception:
        try:
            doc, _ = recover.readfile(filepath)
            ir.add_error("DXF recuperado via ezdxf.recover (arquivo corrompido)")
        except Exception as e2:
            ir.add_error(f"Falha ao abrir DXF: {e2}")
            return ir

    ir._dxf_path = filepath

    insunits = doc.header.get("$INSUNITS", 0)
    scale = INSUNITS_MAP.get(insunits, 1.0)
    ir.unit_scale = scale
    ir.unit_name = _units_name(insunits)

    msp = doc.modelspace()
    _parse_entities(msp, ir, doc)

    return ir


def _units_name(code: int) -> str:
    names = {0: "Sem unidades", 1: "Inches", 2: "Feet", 3: "Miles",
             4: "Millimeters", 5: "Centimeters", 6: "Meters",
             7: "Kilometers", 8: "Microinches", 9: "Mils",
             10: "Yards", 11: "Angstroms", 12: "Nanometers",
             13: "Microns", 14: "Decimeters", 15: "Dekameters",
             16: "Hectometers", 17: "Gigameters", 18: "Astronomical",
             19: "Light Years", 20: "Parsecs"}
    return names.get(code, f"Desconhecido ({code})")


def _parse_entities(entities, ir: GeometryIR, doc) -> None:
    for entity in entities:
        try:
            _dispatch(entity, ir, doc)
        except Exception as e:
            ir.add_error(f"Erro ao processar entidade {entity.dxftype()}: {e}")


def _dispatch(entity, ir: GeometryIR, doc) -> None:
    dxftype = entity.dxftype()
    if dxftype in IGNORED_ENTITIES:
        return
    if not is_layer_allowed(getattr(entity.dxf, "layer", "0")):
        return

    if dxftype == "LINE":
        _parse_line(entity, ir)
    elif dxftype == "ARC":
        _parse_arc(entity, ir)
    elif dxftype == "CIRCLE":
        _parse_circle(entity, ir)
    elif dxftype == "LWPOLYLINE":
        _parse_lwpolyline(entity, ir)
    elif dxftype == "POLYLINE":
        _parse_polyline(entity, ir)
    elif dxftype == "INSERT":
        _parse_insert(entity, ir, doc)
    elif dxftype in ("TEXT", "MTEXT"):
        _parse_text(entity, ir)
    elif dxftype == "SPLINE":
        _parse_spline(entity, ir)
    elif dxftype == "ELLIPSE":
        _parse_ellipse(entity, ir)
    elif dxftype == "HATCH":
        _parse_hatch(entity, ir)
    elif dxftype == "SOLID":
        _parse_solid(entity, ir)
    elif dxftype == "3DFACE":
        _parse_3dface(entity, ir)
    elif dxftype in ("LEADER", "MULTILEADER"):
        _parse_leader(entity, ir)
    elif dxftype == "MLINE":
        _parse_mline(entity, ir)
    elif dxftype == "DIMENSION":
        _parse_dimension(entity, ir)
    elif dxftype == "WIPEOUT":
        pass
    else:
        ir.add_error(f"Entidade não reconhecida ignorada: {dxftype}")


# ─── OCS ──────────────────────────────────────────────────────────

def _ocs_point(entity, point) -> Vec3:
    ext = getattr(entity.dxf, "extrusion", None)
    if ext is not None:
        ocs = OCS(Vec3(ext))
        if ocs.transform:
            return ocs.to_wcs(Vec3(point))
    return Vec3(point)


# ─── LINE ─────────────────────────────────────────────────────────

def _parse_line(entity, ir: GeometryIR) -> None:
    start = _ocs_point(entity, entity.dxf.start)
    end = _ocs_point(entity, entity.dxf.end)
    ir.add_segment(Segment(
        start=Vec2(start.x, start.y),
        end=Vec2(end.x, end.y),
    ))


# ─── ARC ──────────────────────────────────────────────────────────

def _parse_arc(entity, ir: GeometryIR) -> None:
    center = _ocs_point(entity, entity.dxf.center)
    ir.add_arc(Arc(
        center=Vec2(center.x, center.y),
        radius=entity.dxf.radius,
        start_angle=math.radians(entity.dxf.start_angle),
        end_angle=math.radians(entity.dxf.end_angle),
    ))


# ─── CIRCLE ───────────────────────────────────────────────────────

def _parse_circle(entity, ir: GeometryIR) -> None:
    center = _ocs_point(entity, entity.dxf.center)
    ir.add_circle(Circle(
        center=Vec2(center.x, center.y),
        radius=entity.dxf.radius,
    ))


# ─── LWPOLYLINE ───────────────────────────────────────────────────

def _parse_lwpolyline(entity, ir: GeometryIR) -> None:
    points = entity.get_points()
    if len(points) < 2:
        return

    for i in range(len(points) - 1):
        p1 = _lwpoint_to_vec2(points[i])
        p2 = _lwpoint_to_vec2(points[i + 1])
        bulge = _lwpoint_bulge(points[i])

        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
        else:
            arc = _bulge_to_arc(p1, p2, bulge)
            if arc:
                ir.add_arc(arc)

    if entity.closed:
        p_last = _lwpoint_to_vec2(points[-1])
        p_first = _lwpoint_to_vec2(points[0])
        bulge = _lwpoint_bulge(points[-1])
        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=p_last, end=p_first))
        else:
            arc = _bulge_to_arc(p_last, p_first, bulge)
            if arc:
                ir.add_arc(arc)


# ─── POLYLINE ─────────────────────────────────────────────────────

def _parse_polyline(entity, ir: GeometryIR) -> None:
    vertices = list(entity.vertices)
    if len(vertices) < 2:
        return

    for i in range(len(vertices) - 1):
        p1 = vertices[i].dxf.location
        p2 = vertices[i + 1].dxf.location
        bulge = vertices[i].dxf.bulge

        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=Vec2(p1.x, p1.y), end=Vec2(p2.x, p2.y)))
        else:
            arc = _bulge_to_arc(Vec2(p1.x, p1.y), Vec2(p2.x, p2.y), bulge)
            if arc:
                ir.add_arc(arc)

    is_closed = entity.is_closed
    if not is_closed and len(vertices) >= 2:
        p_first = Vec2(vertices[0].dxf.location.x, vertices[0].dxf.location.y)
        p_last = Vec2(vertices[-1].dxf.location.x, vertices[-1].dxf.location.y)
        if p_first.distance(p_last) < 1e-6:
            is_closed = True

    if is_closed:
        p_last = vertices[-1].dxf.location
        p_first = vertices[0].dxf.location
        bulge = vertices[-1].dxf.bulge
        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=Vec2(p_last.x, p_last.y), end=Vec2(p_first.x, p_first.y)))
        else:
            arc = _bulge_to_arc(Vec2(p_last.x, p_last.y), Vec2(p_first.x, p_first.y), bulge)
            if arc:
                ir.add_arc(arc)


# ─── SPLINE ───────────────────────────────────────────────────────

def _parse_spline(entity, ir: GeometryIR) -> None:
    pts = _collect_spline_points(entity)
    if len(pts) < 2:
        return
    ir.add_spline(Spline(control_points=pts, knots=[]))


def _collect_spline_points(entity) -> list:
    raw = entity.control_points if entity.control_points else []
    if len(raw) >= 2:
        pts = [_any_to_vec2(p) for p in raw]
        pts = [p for p in pts if p is not None]
        if len(pts) >= 2:
            return pts
    raw = entity.fit_points if entity.fit_points else []
    if len(raw) >= 2:
        pts = [_any_to_vec2(p) for p in raw]
        pts = [p for p in pts if p is not None]
        if len(pts) >= 2:
            return pts
    return []
    if len(pts) < 2:
        return
    ir.add_spline(Spline(control_points=pts, knots=[]))


# ─── ELLIPSE ──────────────────────────────────────────────────────

def _parse_ellipse(entity, ir: GeometryIR) -> None:
    center = entity.dxf.center
    major = entity.dxf.major_axis
    ir.add_ellipse(Ellipse(
        center=Vec2(center.x, center.y),
        major_axis=Vec2(major.x, major.y),
        ratio=entity.dxf.ratio,
        start_param=entity.dxf.start_param,
        end_param=entity.dxf.end_param,
    ))


# ─── HATCH ────────────────────────────────────────────────────────

def _parse_hatch(entity, ir: GeometryIR) -> None:
    for path in entity.paths:
        _parse_hatch_path(path, ir)


def _parse_hatch_path(path, ir: GeometryIR) -> None:
    vertices = getattr(path, "vertices", None)
    if vertices is not None:
        has_bulge = getattr(path, "has_bulge", lambda: False)()
        n = len(vertices)
        if n < 2:
            return
        for i in range(n - 1):
            p1 = Vec2(vertices[i][0], vertices[i][1])
            p2 = Vec2(vertices[i + 1][0], vertices[i + 1][1])
            bulge = vertices[i][3] if has_bulge and len(vertices[i]) > 3 else 0.0
            if abs(bulge) < 1e-10:
                ir.add_segment(Segment(start=p1, end=p2))
            else:
                arc = _bulge_to_arc(p1, p2, bulge)
                if arc:
                    ir.add_arc(arc)
        is_closed = getattr(path, "is_closed", False)
        if is_closed:
            p_last = Vec2(vertices[-1][0], vertices[-1][1])
            p_first = Vec2(vertices[0][0], vertices[0][1])
            bulge = vertices[-1][3] if has_bulge and len(vertices[-1]) > 3 else 0.0
            if abs(bulge) < 1e-10:
                ir.add_segment(Segment(start=p_last, end=p_first))
            else:
                arc = _bulge_to_arc(p_last, p_first, bulge)
                if arc:
                    ir.add_arc(arc)
        return

    edges = getattr(path, "edges", None)
    if edges:
        for edge in edges:
            _parse_hatch_edge(edge, ir)


def _parse_hatch_edge(edge, ir: GeometryIR) -> None:
    from ezdxf.math import ConstructionArc
    if hasattr(edge, "EDGE_TYPE"):
        edge_type = edge.EDGE_TYPE
    else:
        return

    if edge_type == "LineEdge":
        ir.add_segment(Segment(
            start=Vec2(edge.start.x, edge.start.y),
            end=Vec2(edge.end.x, edge.end.y),
        ))
    elif edge_type == "ArcEdge":
        ir.add_arc(Arc(
            center=Vec2(edge.center.x, edge.center.y),
            radius=edge.radius,
            start_angle=math.radians(edge.start_angle),
            end_angle=math.radians(edge.end_angle),
            ccw=bool(edge.ccw),
        ))
    elif edge_type == "EllipseEdge":
        ir.add_ellipse(Ellipse(
            center=Vec2(edge.center.x, edge.center.y),
            major_axis=Vec2(edge.major_axis.x, edge.major_axis.y),
            ratio=edge.ratio,
            start_param=math.radians(edge.start_angle),
            end_param=math.radians(edge.end_angle),
        ))
    elif edge_type == "SplineEdge":
        cp = [Vec2(p.x, p.y) for p in edge.control_points] if hasattr(edge, 'control_points') else []
        if len(cp) >= 2:
            ir.add_spline(Spline(control_points=cp, knots=[]))


# ─── NOVAS: SOLID, 3DFACE, LEADER, MLINE, DIMENSION ────────────────

def _parse_solid(entity, ir: GeometryIR) -> None:
    vertices = entity.wcs_vertices(close=False)
    for i in range(len(vertices) - 1):
        p1 = Vec2(vertices[i].x, vertices[i].y)
        p2 = Vec2(vertices[i + 1].x, vertices[i + 1].y)
        if p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
    if len(vertices) >= 2:
        p1 = Vec2(vertices[-1].x, vertices[-1].y)
        p0 = Vec2(vertices[0].x, vertices[0].y)
        if p1.distance(p0) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p0))


def _parse_3dface(entity, ir: GeometryIR) -> None:
    vertices = entity.wcs_vertices(close=False)
    for i in range(len(vertices) - 1):
        p1 = Vec2(vertices[i].x, vertices[i].y)
        p2 = Vec2(vertices[i + 1].x, vertices[i + 1].y)
        if p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
    if len(vertices) >= 2:
        p1 = Vec2(vertices[-1].x, vertices[-1].y)
        p0 = Vec2(vertices[0].x, vertices[0].y)
        if p1.distance(p0) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p0))


def _any_to_vec2(v) -> Vec2 | None:
    if v is None:
        return None
    if isinstance(v, tuple):
        return Vec2(float(v[0]), float(v[1]))
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            return Vec2(float(v[0]), float(v[1]))
    except ImportError:
        pass
    try:
        return Vec2(float(v.x), float(v.y))
    except Exception:
        return None


def _parse_leader(entity, ir: GeometryIR) -> None:
    verts = getattr(entity, "vertices", None)
    if verts is None:
        return
    for i in range(len(verts) - 1):
        p1 = _any_to_vec2(verts[i])
        p2 = _any_to_vec2(verts[i + 1])
        if p1 and p2 and p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))


def _parse_mline(entity, ir: GeometryIR) -> None:
    verts = getattr(entity, "vertices", None)
    if verts is None:
        return
    for i in range(len(verts) - 1):
        p1 = _any_to_vec2(verts[i])
        p2 = _any_to_vec2(verts[i + 1])
        if p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))


def _parse_dimension(entity, ir: GeometryIR) -> None:
    def _v(name):
        v = getattr(entity.dxf, name, None)
        return Vec2(v.x, v.y) if v is not None else None

    dp = _v("defpoint")
    dp2 = _v("defpoint2")
    dp3 = _v("defpoint3")
    tm = _v("text_midpoint")

    if dp2 is not None and dp is not None:
        if dp2.distance(dp) > 1e-10:
            ir.add_segment(Segment(start=dp2, end=dp))

    if dp3 is not None and dp is not None:
        if dp3.distance(dp) > 1e-10:
            ir.add_segment(Segment(start=dp3, end=dp))

    if tm is not None:
        ir.add_text(
            getattr(entity.dxf, "text", "") or "Dim",
            layer=entity.dxf.layer,
            position=tm,
        )


# ─── INSERT / BLOCKS ──────────────────────────────────────────────

def _resolve_xref_block(block_name: str, doc, ir: GeometryIR):
    """Tenta resolver um bloco XREF carregando de um arquivo DXF externo."""
    import os as _os

    dxf_path = ir._dxf_path
    if not dxf_path:
        return None

    base_dir = _os.path.dirname(_os.path.abspath(dxf_path))
    candidates = [
        _os.path.join(base_dir, f"{block_name}.dxf"),
        _os.path.join(base_dir, f"{block_name}.DWG"),
        _os.path.join(base_dir, f"{block_name}.dwg"),
    ]

    for candidate in candidates:
        if not _os.path.exists(candidate):
            continue
        try:
            xref_doc = ezdxf.readfile(candidate)
        except Exception:
            continue
        if block_name in xref_doc.blocks:
            src = xref_doc.blocks[block_name]
        else:
            continue
        new_block = doc.blocks.new(block_name)
        for e in src:
            new_block.add_entity(e.copy())
        ir.add_error(f"XREF resolvido: '{block_name}' carregado de '{candidate}'")
        return doc.blocks[block_name]

    return None


MAX_BLOCK_NESTING = 50


def _parse_insert(entity, ir: GeometryIR, doc,
                  acc_insert: Vec2 = Vec2(0, 0),
                  acc_rotation: float = 0.0,
                  acc_x_scale: float = 1.0,
                  acc_y_scale: float = 1.0,
                  _depth: int = 0) -> None:
    if _depth > MAX_BLOCK_NESTING:
        ir.add_error(f"INSERT aninhado >{MAX_BLOCK_NESTING} níveis ignorado (possível referência circular)")
        return

    block_name = entity.dxf.name
    if block_name in doc.blocks:
        block = doc.blocks[block_name]
    else:
        block = _resolve_xref_block(block_name, doc, ir)
        if block is None:
            ir.add_error(f"INSERT ignorado: bloco '{block_name}' não encontrado (XREF não resolvido)")
            return

    local_insert = Vec2(entity.dxf.insert.x, entity.dxf.insert.y)
    local_rotation = math.radians(entity.dxf.rotation if entity.dxf.rotation else 0.0)
    local_x_scale = entity.dxf.xscale if entity.dxf.xscale else 1.0
    local_y_scale = entity.dxf.yscale if entity.dxf.yscale else 1.0

    if abs(local_x_scale) < 1e-10 or abs(local_y_scale) < 1e-10:
        ir.add_error(f"INSERT {block_name} ignorado: escala zero ({local_x_scale}, {local_y_scale})")
        return

    world_insert = _transform_point(local_insert, acc_insert, acc_rotation, acc_x_scale, acc_y_scale)
    world_rotation = acc_rotation + local_rotation
    world_x_scale = acc_x_scale * local_x_scale
    world_y_scale = acc_y_scale * local_y_scale

    for block_entity in block:
        try:
            _parse_block_entity(block_entity, ir, doc,
                                world_insert, world_rotation,
                                world_x_scale, world_y_scale, block_name,
                                _depth=_depth)
        except Exception as e:
            ir.add_error(f"Erro em {block_entity.dxftype()} no bloco {block_name}: {e}")


def _parse_block_entity(block_entity, ir: GeometryIR, doc,
                         insert: Vec2, rotation: float,
                         x_scale: float, y_scale: float,
                         block_name: str,
                         _depth: int = 0) -> None:
    dxftype = block_entity.dxftype()

    if dxftype == "LINE":
        s = block_entity.dxf.start
        e = block_entity.dxf.end
        p1 = _transform_point(Vec2(s.x, s.y), insert, rotation, x_scale, y_scale)
        p2 = _transform_point(Vec2(e.x, e.y), insert, rotation, x_scale, y_scale)
        ir.add_segment(Segment(start=p1, end=p2))

    elif dxftype == "ARC":
        c = block_entity.dxf.center
        center = _transform_point(Vec2(c.x, c.y), insert, rotation, x_scale, y_scale)
        ir.add_arc(Arc(
            center=center,
            radius=block_entity.dxf.radius * max(abs(x_scale), abs(y_scale)),
            start_angle=math.radians(block_entity.dxf.start_angle) + rotation,
            end_angle=math.radians(block_entity.dxf.end_angle) + rotation,
        ))

    elif dxftype == "CIRCLE":
        c = block_entity.dxf.center
        center = _transform_point(Vec2(c.x, c.y), insert, rotation, x_scale, y_scale)
        ir.add_circle(Circle(
            center=center,
            radius=block_entity.dxf.radius * max(abs(x_scale), abs(y_scale)),
        ))

    elif dxftype == "LWPOLYLINE":
        _parse_block_lwpolyline(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype == "SPLINE":
        _parse_block_spline(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype == "ELLIPSE":
        _parse_block_ellipse(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype in ("TEXT", "MTEXT"):
        _parse_block_text(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype == "INSERT":
        _parse_insert(block_entity, ir, doc,
                      acc_insert=insert, acc_rotation=rotation,
                      acc_x_scale=x_scale, acc_y_scale=y_scale,
                      _depth=_depth + 1)

    elif dxftype == "SOLID":
        _parse_block_solid(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype == "3DFACE":
        _parse_block_3dface(block_entity, ir, insert, rotation, x_scale, y_scale)

    elif dxftype == "HATCH":
        _parse_block_hatch(block_entity, ir, insert, rotation, x_scale, y_scale)


def _parse_block_lwpolyline(entity, ir: GeometryIR, insert_point: Vec2,
                             rotation: float, x_scale: float, y_scale: float) -> None:
    points = entity.get_points()
    if len(points) < 2:
        return

    for i in range(len(points) - 1):
        p1 = _transform_point(_lwpoint_to_vec2(points[i]), insert_point, rotation, x_scale, y_scale)
        p2 = _transform_point(_lwpoint_to_vec2(points[i + 1]), insert_point, rotation, x_scale, y_scale)
        bulge = _lwpoint_bulge(points[i])

        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
        else:
            arc = _bulge_to_arc(p1, p2, bulge)
            if arc:
                ir.add_arc(arc)

    if getattr(entity, "closed", False):
        p_last = _transform_point(_lwpoint_to_vec2(points[-1]), insert_point, rotation, x_scale, y_scale)
        p_first = _transform_point(_lwpoint_to_vec2(points[0]), insert_point, rotation, x_scale, y_scale)
        bulge = _lwpoint_bulge(points[-1])
        if abs(bulge) < 1e-10:
            ir.add_segment(Segment(start=p_last, end=p_first))
        else:
            arc = _bulge_to_arc(p_last, p_first, bulge)
            if arc:
                ir.add_arc(arc)


def _parse_block_spline(entity, ir: GeometryIR, insert_point: Vec2,
                         rotation: float, x_scale: float, y_scale: float) -> None:
    cpts = entity.control_points
    if len(cpts) < 2:
        return
    pts = [_any_to_vec2(p) for p in cpts]
    pts = [p for p in pts if p is not None]
    if len(pts) < 2:
        return
    transformed = [
        _transform_point(p, insert_point, rotation, x_scale, y_scale)
        for p in pts
    ]
    ir.add_spline(Spline(control_points=transformed, knots=[]))


def _parse_block_ellipse(entity, ir: GeometryIR, insert_point: Vec2,
                          rotation: float, x_scale: float, y_scale: float) -> None:
    center = _transform_point(
        Vec2(entity.dxf.center.x, entity.dxf.center.y),
        insert_point, rotation, x_scale, y_scale)
    major = entity.dxf.major_axis
    major_transformed = Vec2(
        major.x * x_scale * math.cos(rotation) - major.y * y_scale * math.sin(rotation),
        major.x * x_scale * math.sin(rotation) + major.y * y_scale * math.cos(rotation),
    )
    ir.add_ellipse(Ellipse(
        center=center,
        major_axis=major_transformed,
        ratio=entity.dxf.ratio,
        start_param=entity.dxf.start_param + rotation,
        end_param=entity.dxf.end_param + rotation,
    ))


def _parse_block_text(entity, ir: GeometryIR, insert_point: Vec2,
                       rotation: float, x_scale: float, y_scale: float) -> None:
    text = entity.dxf.text
    ins = getattr(entity.dxf, 'insert', None)
    if ins:
        pos = _transform_point(Vec2(ins.x, ins.y), insert_point, rotation, x_scale, y_scale)
        ir.add_text(text, layer=entity.dxf.layer, position=pos)


def _parse_block_solid(entity, ir: GeometryIR, insert_point: Vec2,
                        rotation: float, x_scale: float, y_scale: float) -> None:
    vertices = [Vec2(v.x, v.y) for v in entity.wcs_vertices(close=False)]
    for i in range(len(vertices) - 1):
        p1 = _transform_point(vertices[i], insert_point, rotation, x_scale, y_scale)
        p2 = _transform_point(vertices[i + 1], insert_point, rotation, x_scale, y_scale)
        if p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
    if len(vertices) >= 2:
        p1 = _transform_point(vertices[-1], insert_point, rotation, x_scale, y_scale)
        p0 = _transform_point(vertices[0], insert_point, rotation, x_scale, y_scale)
        if p1.distance(p0) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p0))


def _parse_block_3dface(entity, ir: GeometryIR, insert_point: Vec2,
                         rotation: float, x_scale: float, y_scale: float) -> None:
    vertices = [Vec2(v.x, v.y) for v in entity.wcs_vertices(close=False)]
    for i in range(len(vertices) - 1):
        p1 = _transform_point(vertices[i], insert_point, rotation, x_scale, y_scale)
        p2 = _transform_point(vertices[i + 1], insert_point, rotation, x_scale, y_scale)
        if p1.distance(p2) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p2))
    if len(vertices) >= 2:
        p1 = _transform_point(vertices[-1], insert_point, rotation, x_scale, y_scale)
        p0 = _transform_point(vertices[0], insert_point, rotation, x_scale, y_scale)
        if p1.distance(p0) > 1e-10:
            ir.add_segment(Segment(start=p1, end=p0))


def _parse_block_hatch(entity, ir: GeometryIR, insert_point: Vec2,
                        rotation: float, x_scale: float, y_scale: float) -> None:
    _parse_hatch(entity, ir)


# ─── HELPERS ──────────────────────────────────────────────────────

def _lwpoint_to_vec2(point) -> Vec2:
    if isinstance(point, tuple):
        return Vec2(float(point[0]), float(point[1]))
    return point.vec2


def _lwpoint_bulge(point) -> float:
    if isinstance(point, tuple):
        return float(point[4]) if len(point) > 4 else 0.0
    return point.bulge


def _parse_text(entity, ir: GeometryIR) -> None:
    text = entity.dxf.text
    ins = getattr(entity.dxf, 'insert', None)
    position = Vec2(ins.x, ins.y) if ins else None
    ir.add_text(text, layer=entity.dxf.layer, position=position)


def _transform_point(point: Vec2, insert: Vec2,
                     rotation: float, x_scale: float, y_scale: float) -> Vec2:
    scaled = Vec2(point.x * x_scale, point.y * y_scale)
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    rotated = Vec2(
        scaled.x * cos_r - scaled.y * sin_r,
        scaled.x * sin_r + scaled.y * cos_r,
    )
    return insert + rotated


def _bulge_to_arc(p1: Vec2, p2: Vec2, bulge: float) -> Optional[Arc]:
    if abs(bulge) < 1e-10:
        return None

    chord = p1.distance(p2)
    if chord < 1e-10:
        return None

    sagitta = bulge * chord / 2
    radius = abs((chord / 2) * (chord / 2) / sagitta + sagitta) / 2

    mid = (p1 + p2) / 2
    perp = Vec2(-(p2.y - p1.y), p2.x - p1.x).normalize()
    center = mid + perp * (sagitta - (chord / 2) * (chord / 2) / (4 * sagitta))

    start_angle = math.atan2(p1.y - center.y, p1.x - center.x)
    end_angle = math.atan2(p2.y - center.y, p2.x - center.x)

    ccw = bulge > 0

    return Arc(
        center=center,
        radius=abs(radius),
        start_angle=start_angle,
        end_angle=end_angle,
        ccw=ccw,
    )
