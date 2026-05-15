from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ezdxf.math import Vec2


@dataclass
class Segment:
    start: Vec2
    end: Vec2

    def length(self) -> float:
        return self.start.distance(self.end)

    def reversed(self) -> Segment:
        return Segment(start=self.end, end=self.start)

    def to_tuple(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        return ((self.start.x, self.start.y), (self.end.x, self.end.y))


@dataclass
class Arc:
    center: Vec2
    radius: float
    start_angle: float
    end_angle: float
    ccw: bool = True


@dataclass
class Circle:
    center: Vec2
    radius: float


@dataclass
class Spline:
    control_points: List[Vec2]
    knots: List[float]


@dataclass
class Ellipse:
    center: Vec2
    major_axis: Vec2
    ratio: float
    start_param: float
    end_param: float


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
    errors: List[str] = field(default_factory=list)
    unit_scale: float = 1.0
    unit_name: str = "Meters"
    _dxf_path: str = ""

    def add_segment(self, seg: Segment) -> None:
        self.segments.append(seg)

    def add_arc(self, arc: Arc) -> None:
        self.arcs.append(arc)

    def add_circle(self, circle: Circle) -> None:
        self.circles.append(circle)

    def add_spline(self, spline: Spline) -> None:
        self.splines.append(spline)

    def add_ellipse(self, ellipse: Ellipse) -> None:
        self.ellipses.append(ellipse)

    def add_text(self, text: str, layer: str = "", position: Vec2 | None = None) -> None:
        self.texts.append({"texto": text, "layer": layer,
                           "position": {"x": position.x, "y": position.y} if position else None})

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def __bool__(self) -> bool:
        return bool(self.segments or self.arcs or self.circles or self.splines or self.ellipses)
