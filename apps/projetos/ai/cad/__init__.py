from apps.projetos.ai.cad.engine import process_dxf, EngineResult
from apps.projetos.ai.cad.ir import (
    GeometryIR, Segment, Arc, Circle, Spline, Ellipse, Ring, Polygon,
)
from apps.projetos.ai.cad.config import CadConfig, get_cad_config, is_layer_allowed
from apps.projetos.ai.cad.dxf_parser import parse_dxf
from apps.projetos.ai.cad.curve_resolution import flatten_curves
from apps.projetos.ai.cad.healer import heal
from apps.projetos.ai.cad.polygonizer import polygonize_segments, PolygonizeResult
from apps.projetos.ai.cad.validation import validate_polygons
from apps.projetos.ai.cad.metrics import compute_metrics, MetricResult, RoomMetrics
from apps.projetos.ai.cad.classifier import classify_rooms
from apps.projetos.ai.cad.topology import TopologyGraph
from apps.projetos.ai.cad.geojson import to_geojson

__all__ = [
    "process_dxf", "EngineResult",
    "GeometryIR", "Segment", "Arc", "Circle", "Spline", "Ellipse", "Ring", "Polygon",
    "CadConfig", "get_cad_config", "is_layer_allowed",
    "parse_dxf",
    "flatten_curves",
    "heal",
    "polygonize_segments", "PolygonizeResult",
    "validate_polygons",
    "compute_metrics", "MetricResult", "RoomMetrics",
    "classify_rooms",
    "TopologyGraph",
    "to_geojson",
]
