from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ezdxf.math import Vec2


def _as_vec2(v):
    if isinstance(v, Vec2):
        return v
    if isinstance(v, (tuple, list)):
        return Vec2(float(v[0]), float(v[1]))
    return Vec2(float(v.x), float(v.y))


@dataclass
class Segment:
    start: Vec2
    end: Vec2
    layer: str = ""

    def __post_init__(self):
        if not isinstance(self.start, Vec2):
            object.__setattr__(self, 'start', _as_vec2(self.start))
        if not isinstance(self.end, Vec2):
            object.__setattr__(self, 'end', _as_vec2(self.end))

    def length(self) -> float:
        return self.start.distance(self.end)

    def reversed(self) -> Segment:
        return Segment(start=self.end, end=self.start, layer=self.layer)

    def to_tuple(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        return ((self.start.x, self.start.y), (self.end.x, self.end.y))


@dataclass
class Arc:
    center: Vec2
    radius: float
    start_angle: float
    end_angle: float
    ccw: bool = True
    layer: str = ""


@dataclass
class Circle:
    center: Vec2
    radius: float
    layer: str = ""


@dataclass
class Spline:
    control_points: List[Vec2]
    knots: List[float]
    layer: str = ""


@dataclass
class Ellipse:
    center: Vec2
    major_axis: Vec2
    ratio: float
    start_param: float
    end_param: float
    layer: str = ""


@dataclass
class Ring:
    vertices: List[Vec2]

    def is_closed(self) -> bool:
        if len(self.vertices) < 2:
            return False
        return self.vertices[0].distance(self.vertices[-1]) < 1e-10

    def to_segments(self) -> List[Segment]:
        segs: List[Segment] = []
        for i in range(len(self.vertices) - 1):
            segs.append(Segment(start=self.vertices[i], end=self.vertices[i + 1]))
        return segs


@dataclass
class Polygon:
    outer: Ring
    holes: List[Ring] = field(default_factory=list)


@dataclass
class GeometryIR:
    segments: List[Segment] = field(default_factory=list)
    arcs: List[Arc] = field(default_factory=list)
    circles: List[Circle] = field(default_factory=list)
    splines: List[Spline] = field(default_factory=list)
    ellipses: List[Ellipse] = field(default_factory=list)
    texts: List[dict] = field(default_factory=list)
    blocks: List[dict] = field(default_factory=list)
    dimensions: List[dict] = field(default_factory=list)
    entities_by_layer: dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    unit_scale: float = 1.0
    unit_name: str = "Meters"
    _dxf_path: str = ""
    current_layer: str = ""

    def add_segment(self, seg: Segment) -> None:
        if not seg.layer:
            seg.layer = self.current_layer
        self.segments.append(seg)

    def add_arc(self, arc: Arc) -> None:
        if not arc.layer:
            arc.layer = self.current_layer
        self.arcs.append(arc)

    def add_circle(self, circle: Circle) -> None:
        if not circle.layer:
            circle.layer = self.current_layer
        self.circles.append(circle)

    def add_spline(self, spline: Spline) -> None:
        if not spline.layer:
            spline.layer = self.current_layer
        self.splines.append(spline)

    def add_ellipse(self, ellipse: Ellipse) -> None:
        if not ellipse.layer:
            ellipse.layer = self.current_layer
        self.ellipses.append(ellipse)

    def add_text(self, text: str, layer: str = "", position: Vec2 | tuple | list | None = None) -> None:
        pos = None
        if position is not None:
            if isinstance(position, Vec2):
                pos = {"x": position.x, "y": position.y}
            else:
                pos = {"x": float(position[0]), "y": float(position[1])}
        self.texts.append({"texto": text, "layer": layer, "position": pos})

    def add_block(self, name: str, layer: str, position: Vec2, rotation: float = 0.0,
                  x_scale: float = 1.0, y_scale: float = 1.0) -> None:
        self.blocks.append({
            "nome": name, "layer": layer,
            "pos_x": round(position.x, 4), "pos_y": round(position.y, 4),
            "rotacao": round(rotation, 2), "escala_x": round(x_scale, 4), "escala_y": round(y_scale, 4),
        })

    def add_dimension(self, text: str, layer: str, measurement: float,
                      defpoint, defpoint2, defpoint3) -> None:
        dp = {"x": round(defpoint.x, 4), "y": round(defpoint.y, 4)} if defpoint else None
        dp2 = {"x": round(defpoint2.x, 4), "y": round(defpoint2.y, 4)} if defpoint2 else None
        dp3 = {"x": round(defpoint3.x, 4), "y": round(defpoint3.y, 4)} if defpoint3 else None
        self.dimensions.append({
            "texto": text, "layer": layer, "medida": round(measurement, 4),
            "ponto1": dp, "ponto2": dp2, "ponto3": dp3,
        })

    def track_entity(self, layer: str, dxftype: str) -> None:
        if layer not in self.entities_by_layer:
            self.entities_by_layer[layer] = {}
        ent_types = self.entities_by_layer[layer]
        ent_types[dxftype] = ent_types.get(dxftype, 0) + 1

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def __bool__(self) -> bool:
        return bool(self.segments or self.arcs or self.circles or self.splines or self.ellipses)
