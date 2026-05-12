"""
geojson_builder.py
==================
Constrói GeoJSON limpo a partir das entidades extraídas pelo dxf_reader.

Monta FeatureCollection com propriedades enriquecidas (layer, tipo, handle,
categoria do classificador, etc.).
"""

import json
from typing import List, Optional


# ── Mapeamento de SubClasses por tipo de entidade ───────────────────────────

_SUBCLASSES = {
    "LWPOLYLINE": "AcDbPolyline",
    "POLYLINE": "AcDbPolyline",
    "LINE": "AcDbLine",
    "ARC": "AcDbArc",
    "CIRCLE": "AcDbCircle",
    "SPLINE": "AcDbSpline",
    "ELLIPSE": "AcDbEllipse",
}


def _entidade_para_feature(entidade: dict, categoria: Optional[str] = None) -> dict:
    """
    Converte uma entidade estruturada (do dxf_reader) para Feature GeoJSON.

    Parâmetros:
        entidade  : dict com keys 'tipo', 'layer', 'handle', 'geometria'
        categoria : categoria inferida pelo classificador (opcional)
    """
    geometria = entidade["geometria"]

    feature = {
        "type": "Feature",
        "geometry": {
            "type": geometria["tipo_geometria"],
            "coordinates": geometria["coordenadas"],
        },
        "properties": {
            "Layer": entidade["layer"],
            "SubClasses": _SUBCLASSES.get(entidade["tipo"], "AcDbEntity"),
            "EntityHandle": entidade["handle"],
            "tipo_entidade": entidade["tipo"],
            "fechada": geometria.get("fechada", False),
        },
    }

    # Propriedades opcionais
    if "raio" in geometria:
        feature["properties"]["raio"] = geometria["raio"]

    if categoria:
        feature["properties"]["categoria"] = categoria

    return feature


def construir_geojson(
    entidades: List[dict],
    mapa_categorias: Optional[dict] = None,
) -> dict:
    """
    Constrói um objeto GeoJSON FeatureCollection a partir das entidades.

    Parâmetros:
        entidades        : lista de entidades do dxf_reader
        mapa_categorias  : dict mapeando layer → categoria (do classificador)

    Retorna:
        dict GeoJSON FeatureCollection
    """
    features = []

    for ent in entidades:
        categoria = None
        if mapa_categorias:
            categoria = mapa_categorias.get(ent["layer"])

        feature = _entidade_para_feature(ent, categoria)
        if feature:
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def salvar_geojson(geojson: dict, caminho_saida: str) -> str:
    """Salva o GeoJSON em disco e retorna o caminho."""
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"   💾 GeoJSON salvo: {caminho_saida} ({len(geojson['features'])} features)")
    return caminho_saida
