"""
filters.py
==========
Regras de filtragem para entidades DXF.

Separa entidades geométricas relevantes (pilares, vigas, lajes, etc.)
de ruído visual (cotas, hachuras, textos, blocos de anotação).
"""

# ── Tipos de entidade DXF que contêm geometria estrutural real ──────────────
TIPOS_GEOMETRICOS = frozenset({
    "LWPOLYLINE",
    "POLYLINE",
    "LINE",
    "ARC",
    "CIRCLE",
    "SPLINE",
    "ELLIPSE",
})

# ── Tipos de entidade DXF que são anotação/decoração (nunca estruturais) ────
TIPOS_IGNORADOS = frozenset({
    "DIMENSION",
    "LEADER",
    "MULTILEADER",
    "HATCH",
    "MTEXT",
    "TEXT",
    "INSERT",
    "VIEWPORT",
    "WIPEOUT",
    "SOLID",
    "3DFACE",
    "3DSOLID",
    "ATTDEF",
    "ATTRIB",
    "POINT",
    "RAY",
    "XLINE",
    "REGION",
    "BODY",
    "OLEFRAME",
    "OLE2FRAME",
    "IMAGE",
    "TOLERANCE",
    "TABLE",
    "ACAD_TABLE",
})

# ── Layers que normalmente são anotação/suporte (case-insensitive) ──────────
LAYERS_IGNORADAS = frozenset({
    "COTAS",
    "TEXTOS",
    "CARIMBO",
    "HACHURA",
    "DIM",
    "ANOTAÇÃO",
    "ANOTACAO",
    "LEGENDA",
    "GRID",
    "EIXOS",
    "EIXO",
    "PROJEÇÃO",
    "PROJECAO",
    "DEFPOINTS",
    "VIEWPORT",
    "TÍTULO",
    "TITULO",
    "MARGEM",
    "SELO",
    "QUADRO",
    "NORTE",
})

# ── Substrings em nomes de layer que indicam anotação ───────────────────────
LAYER_SUBSTRINGS_IGNORADAS = (
    "COTA",
    "DIM",
    "TEXT",
    "ANNOT",
    "HATCH",
    "LEGENDA",
    "CARIMBO",
    "GRID",
    "EIXO",
)


def tipo_eh_geometrico(tipo_entidade: str) -> bool:
    """Retorna True se o tipo DXF representa geometria processável."""
    return tipo_entidade in TIPOS_GEOMETRICOS


def tipo_eh_ignorado(tipo_entidade: str) -> bool:
    """Retorna True se o tipo DXF é anotação/decoração que deve ser descartada."""
    return tipo_entidade in TIPOS_IGNORADOS


def layer_eh_ignorada(nome_layer: str) -> bool:
    """
    Retorna True se a layer deve ser ignorada por ser de anotação/suporte.

    Verifica tanto correspondência exata (case-insensitive) quanto
    presença de substrings conhecidas.
    """
    layer_upper = nome_layer.strip().upper()

    # Correspondência exata
    if layer_upper in LAYERS_IGNORADAS:
        return True

    # Correspondência por substring
    for substr in LAYER_SUBSTRINGS_IGNORADAS:
        if substr in layer_upper:
            return True

    return False


def entidade_deve_ser_processada(tipo_entidade: str, nome_layer: str) -> bool:
    """
    Decide se uma entidade DXF deve ser incluída no processamento.

    Retorna True somente se:
      1. O tipo é geométrico (LWPOLYLINE, LINE, ARC, etc.)
      2. O tipo NÃO é de anotação (DIMENSION, HATCH, etc.)
      3. A layer NÃO é de anotação (COTAS, TEXTOS, etc.)
    """
    if tipo_eh_ignorado(tipo_entidade):
        return False

    if not tipo_eh_geometrico(tipo_entidade):
        return False

    if layer_eh_ignorada(nome_layer):
        return False

    return True
