from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class CadConfig:
    epsilon: float = field(default_factory=lambda: float(os.getenv("CAD_EPSILON", "0.001")))
    snap_radius: float = field(default_factory=lambda: float(os.getenv("CAD_SNAP_RADIUS", "0.01")))
    flatten_epsilon: float = field(default_factory=lambda: float(os.getenv("CAD_FLATTEN_EPSILON", "0.0001")))
    min_area: float = field(default_factory=lambda: float(os.getenv("CAD_MIN_AREA", "0.01")))
    classifier_max_distance: float = field(default_factory=lambda: float(os.getenv("CAD_CLASSIFIER_MAX_DIST", "5.0")))
    layer_whitelist: str = field(default_factory=lambda: os.getenv("CAD_LAYER_WHITELIST", ""))
    layer_blacklist: str = field(default_factory=lambda: os.getenv("CAD_LAYER_BLACKLIST", ""))
    skip_graph: bool = field(default_factory=lambda: os.getenv("CAD_SKIP_GRAPH", "").lower() in ("1", "true", "yes"))
    batch_size: int = field(default_factory=lambda: int(os.getenv("CAD_BATCH_SIZE", "50000")))


config = CadConfig()


def get_layer_whitelist() -> list:
    return [l.strip() for l in config.layer_whitelist.split(",") if l.strip()]


def get_layer_blacklist() -> list:
    return [l.strip() for l in config.layer_blacklist.split(",") if l.strip()]


def is_layer_allowed(layer_name: str) -> bool:
    wl = get_layer_whitelist()
    bl = get_layer_blacklist()
    if wl and layer_name not in wl:
        return False
    if bl and layer_name in bl:
        return False
    return True
