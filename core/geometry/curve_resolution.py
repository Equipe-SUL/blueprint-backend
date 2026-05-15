from __future__ import annotations

import math
from typing import List

from ezdxf.math import Vec2

from core.config import config
from core.geometry.ir import GeometryIR, Segment, Arc, Circle, Spline, Ellipse


def flatten_curves(ir: GeometryIR, epsilon: float | None = None) -> List[Segment]:
    epsilon = epsilon if epsilon is not None else config.flatten_epsilon
    result = list(ir.segments)
    for arc in ir.arcs:
        result.extend(flatten_arc(arc, epsilon))
    for circle in ir.circles:
        result.extend(flatten_circle(circle, epsilon))
    for spline in ir.splines:
        result.extend(flatten_spline(spline, epsilon))
    for ellipse in ir.ellipses:
        result.extend(flatten_ellipse(ellipse, epsilon))
    return result


def flatten_arc(arc: Arc, epsilon: float) -> List[Segment]:
    if arc.radius < epsilon:
        return []

    sweep = arc.end_angle - arc.start_angle
    if not arc.ccw and sweep > 0:
        sweep -= 2 * math.pi
    elif arc.ccw and sweep < 0:
        sweep += 2 * math.pi

    abs_sweep = abs(sweep)
    num_segments = max(4, int(abs_sweep / (2 * math.acos(1 - epsilon / arc.radius))) + 1)
    angle_step = sweep / num_segments
    segments: List[Segment] = []

    for i in range(num_segments):
        a1 = arc.start_angle + i * angle_step
        a2 = arc.start_angle + (i + 1) * angle_step
        p1 = Vec2(arc.center.x + arc.radius * math.cos(a1),
                   arc.center.y + arc.radius * math.sin(a1))
        p2 = Vec2(arc.center.x + arc.radius * math.cos(a2),
                   arc.center.y + arc.radius * math.sin(a2))
        segments.append(Segment(start=p1, end=p2))

    return segments


def flatten_circle(circle: Circle, epsilon: float) -> List[Segment]:
    arc = Arc(center=circle.center, radius=circle.radius,
              start_angle=0.0, end_angle=2 * math.pi, ccw=True)
    return flatten_arc(arc, epsilon)


def flatten_spline(spline: Spline, epsilon: float) -> List[Segment]:
    cpts = spline.control_points
    if len(cpts) < 2:
        return []

    n = max(2, len(cpts) * 10)
    segments: List[Segment] = []

    for i in range(n):
        t = i / n
        p1 = _eval_spline(cpts, t)
        p2 = _eval_spline(cpts, (i + 1) / n)
        if p1.distance(p2) > epsilon:
            segments.append(Segment(start=p1, end=p2))

    return segments


def _eval_spline(cpts: List[Vec2], t: float) -> Vec2:
    n = len(cpts) - 1
    x, y = 0.0, 0.0
    for i, cp in enumerate(cpts):
        b = _bernstein(n, i, t)
        x += cp.x * b
        y += cp.y * b
    return Vec2(x, y)


def _bernstein(n: int, i: int, t: float) -> float:
    return _binom(n, i) * (t ** i) * ((1 - t) ** (n - i))


def _binom(n: int, k: int) -> float:
    if k < 0 or k > n:
        return 0.0
    if k == 0 or k == n:
        return 1.0
    k = min(k, n - k)
    result = 1.0
    for i in range(1, k + 1):
        result = result * (n - k + i) / i
    return result


def flatten_ellipse(ellipse: Ellipse, epsilon: float) -> List[Segment]:
    cx, cy = ellipse.center.x, ellipse.center.y
    a = ellipse.major_axis.magnitude
    if a < epsilon:
        return []
    b = a * ellipse.ratio
    angle = math.atan2(ellipse.major_axis.y, ellipse.major_axis.x)

    sweep = ellipse.end_param - ellipse.start_param
    if sweep <= 0:
        sweep += 2 * math.pi

    abs_sweep = abs(sweep)
    num_segments = max(4, int(abs_sweep / (2 * math.acos(1 - epsilon / max(a, b, epsilon)))) + 1)
    step = sweep / num_segments
    segments: List[Segment] = []

    for i in range(num_segments):
        t1 = ellipse.start_param + i * step
        t2 = ellipse.start_param + (i + 1) * step
        p1 = _ellipse_point(cx, cy, a, b, angle, t1)
        p2 = _ellipse_point(cx, cy, a, b, angle, t2)
        segments.append(Segment(start=p1, end=p2))

    return segments


def _ellipse_point(cx: float, cy: float, a: float, b: float,
                   angle: float, t: float) -> Vec2:
    cos_t = math.cos(t)
    sin_t = math.sin(t)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = cx + a * cos_t * cos_a - b * sin_t * sin_a
    y = cy + a * cos_t * sin_a + b * sin_t * cos_a
    return Vec2(x, y)
