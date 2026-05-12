"""
taxonomy.py
===========
Taxonomia de elementos estruturais para projetos de construção civil.

Define as categorias válidas, regras hardcoded para layers conhecidas,
e mapeamento de categorias para descrições SINAPI.
"""

# ── Categorias válidas de elementos estruturais ─────────────────────────────

CATEGORIAS_VALIDAS = frozenset({
    "pilar",
    "viga",
    "laje",
    "estaca",
    "fundacao",
    "parede",
    "tubulacao",
    "eletrica",
    "anotacao",
    "desconhecido",
})

# ── Categorias que devem ser descartadas após classificação ─────────────────

CATEGORIAS_DESCARTAVEIS = frozenset({
    "anotacao",
    "eletrica",
    "desconhecido",
})

# ── Categorias que representam elementos estruturais reais ──────────────────

CATEGORIAS_ESTRUTURAIS = frozenset({
    "pilar",
    "viga",
    "laje",
    "estaca",
    "fundacao",
    "parede",
})

# ── Mapeamento estático de layers conhecidas → categoria ────────────────────
# (case-insensitive, verificado com .upper())

MAPA_LAYERS_CONHECIDAS = {
    # Pilares
    "PILAR": "pilar",
    "PILARES": "pilar",
    "P-PILAR": "pilar",
    "EST-PILAR": "pilar",
    "ESTRUTURA_PILAR": "pilar",
    "S-PILAR": "pilar",
    "STR-PILAR": "pilar",
    "PILAR-CONC": "pilar",
    "PIL": "pilar",

    # Vigas
    "VIGA": "viga",
    "VIGAS": "viga",
    "V-VIGA": "viga",
    "EST-VIGA": "viga",
    "ESTRUTURA_VIGA": "viga",
    "S-VIGA": "viga",
    "STR-VIGA": "viga",
    "VIGA-CONC": "viga",
    "VIG": "viga",

    # Lajes
    "LAJE": "laje",
    "LAJES": "laje",
    "L-LAJE": "laje",
    "EST-LAJE": "laje",
    "ESTRUTURA_LAJE": "laje",
    "S-LAJE": "laje",
    "STR-LAJE": "laje",
    "LAJE-CONC": "laje",

    # Estacas
    "ESTACA": "estaca",
    "ESTACAS": "estaca",
    "E-ESTACA": "estaca",
    "EST-ESTACA": "estaca",
    "FUNDACAO_ESTACA": "estaca",
    "ESTACA-CONC": "estaca",

    # Fundações
    "FUNDACAO": "fundacao",
    "FUNDAÇÃO": "fundacao",
    "FUNDACOES": "fundacao",
    "F-FUNDACAO": "fundacao",
    "SAPATA": "fundacao",
    "BLOCO": "fundacao",
    "RADIER": "fundacao",
    "BALDRAME": "fundacao",

    # Paredes
    "PAREDE": "parede",
    "PAREDES": "parede",
    "ALVENARIA": "parede",
    "ALV": "parede",
    "VEDACAO": "parede",
    "VEDAÇÃO": "parede",
    "MURO": "parede",

    # Tubulação
    "TUBULACAO": "tubulacao",
    "TUBULAÇÃO": "tubulacao",
    "HIDRAULICA": "tubulacao",
    "HIDRÁULICA": "tubulacao",
    "ESGOTO": "tubulacao",
    "AGUA": "tubulacao",
    "ÁGUA": "tubulacao",
    "INCENDIO": "tubulacao",
    "INCÊNDIO": "tubulacao",

    # Elétrica
    "ELETRICA": "eletrica",
    "ELÉTRICA": "eletrica",
    "ILUMINACAO": "eletrica",
    "ILUMINAÇÃO": "eletrica",
    "TOMADA": "eletrica",
    "QUADRO_ELETRICO": "eletrica",

    # Anotação
    "COTAS": "anotacao",
    "TEXTOS": "anotacao",
    "CARIMBO": "anotacao",
    "HACHURA": "anotacao",
    "LEGENDA": "anotacao",
    "GRID": "anotacao",
    "EIXOS": "anotacao",
    "DEFPOINTS": "anotacao",
}


# ── Mapeamento de categoria → descrição para busca SINAPI ──────────────────

MAPA_CATEGORIA_SINAPI = {
    "pilar": {
        "type": "pilar",
        "description": "Pilar de concreto armado",
        "campo_qty": "area_m2",
        "unidade": "m2",
    },
    "viga": {
        "type": "viga",
        "description": "Viga de concreto armado",
        "campo_qty": "comprimento_m",
        "unidade": "m",
    },
    "estaca": {
        "type": "estaca",
        "description": "Estaca de concreto armado",
        "campo_qty": "area_m2",
        "unidade": "m2",
    },
    "laje": {
        "type": "laje",
        "description": "Laje de concreto armado",
        "campo_qty": "area_m2",
        "unidade": "m2",
    },
    "fundacao": {
        "type": "fundacao",
        "description": "Fundação de concreto armado",
        "campo_qty": "area_m2",
        "unidade": "m2",
    },
    "parede": {
        "type": "parede",
        "description": "Alvenaria de vedação",
        "campo_qty": "area_m2",
        "unidade": "m2",
    },
    "tubulacao": {
        "type": "tubulacao",
        "description": "Tubulação hidráulica",
        "campo_qty": "comprimento_m",
        "unidade": "m",
    },
}


def classificar_layer_por_regra(nome_layer: str) -> str:
    """
    Classifica uma layer por regras determinísticas (sem IA).

    Primeiro tenta correspondência exata (case-insensitive),
    depois tenta correspondência por substring.

    Retorna a categoria ou "desconhecido" se não encontrar.
    """
    layer_upper = nome_layer.strip().upper()

    # Correspondência exata
    if layer_upper in MAPA_LAYERS_CONHECIDAS:
        return MAPA_LAYERS_CONHECIDAS[layer_upper]

    # Correspondência por substring (palavras-chave)
    _KEYWORDS = {
        "PILAR": "pilar",
        "PIL": "pilar",
        "COLUMN": "pilar",
        "VIGA": "viga",
        "VIG": "viga",
        "BEAM": "viga",
        "LAJE": "laje",
        "SLAB": "laje",
        "ESTACA": "estaca",
        "PILE": "estaca",
        "FUNDACAO": "fundacao",
        "FUNDAÇÃO": "fundacao",
        "FOUNDATION": "fundacao",
        "SAPATA": "fundacao",
        "PAREDE": "parede",
        "WALL": "parede",
        "ALV": "parede",
    }

    for keyword, categoria in _KEYWORDS.items():
        if keyword in layer_upper:
            return categoria

    return "desconhecido"
