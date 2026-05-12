"""
geometry.py
===========
Cálculos geométricos determinísticos para entidades DXF.

Inclui:
  - Área (fórmula de Gauss / Shoelace)
  - Perímetro / Comprimento
  - Detecção de anel fechado
  - Remoção de coordenada Z
  - Aproximação de arcos e círculos por pontos
"""

import math
from typing import List, Tuple

Coord2D = Tuple[float, float]


# ── Utilitários de coordenadas ──────────────────────────────────────────────

def remover_z(pontos: list) -> List[Coord2D]:
    """
    Remove a coordenada Z, mantendo apenas (x, y).
    Converte numpy.float64 → float nativo do Python para evitar
    erros de serialização no checkpointer do LangGraph (msgpack).
    """
    return [(float(p[0]), float(p[1])) for p in pontos]


def esta_fechada(coords: List[Coord2D], tolerancia: float = 1e-9) -> bool:
    """Verifica se uma sequência de coordenadas forma um anel fechado."""
    if len(coords) < 3:
        return False
    dx = abs(coords[0][0] - coords[-1][0])
    dy = abs(coords[0][1] - coords[-1][1])
    return dx < tolerancia and dy < tolerancia


def fechar_anel(coords: List[Coord2D]) -> List[Coord2D]:
    """Garante que o primeiro e o último ponto sejam iguais."""
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


# ── Aproximação de arcos e círculos ─────────────────────────────────────────

def arco_para_pontos(
    cx: float, cy: float, raio: float,
    angulo_inicio_graus: float, angulo_fim_graus: float,
    segmentos: int = 64,
) -> List[Coord2D]:
    """Aproxima um arco por uma lista de pontos (x, y)."""
    inicio = math.radians(angulo_inicio_graus)
    fim = math.radians(angulo_fim_graus)
    if fim < inicio:
        fim += 2 * math.pi
    angulos = [inicio + (fim - inicio) * i / segmentos for i in range(segmentos + 1)]
    return [(cx + raio * math.cos(a), cy + raio * math.sin(a)) for a in angulos]


def circulo_para_poligono(
    cx: float, cy: float, raio: float, segmentos: int = 64
) -> List[Coord2D]:
    """Aproxima um círculo por um polígono fechado."""
    pontos = arco_para_pontos(cx, cy, raio, 0, 360, segmentos)
    pontos.append(pontos[0])  # fecha o anel
    return pontos


# ── Cálculos de área e perímetro ────────────────────────────────────────────

def calcular_area(anel: List[Coord2D]) -> float:
    """
    Calcula a área de um anel usando a fórmula de Gauss (Shoelace).
    Retorna a área em unidades do sistema de coordenadas (m², cm², etc.).
    """
    n = len(anel)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += anel[i][0] * anel[j][1]
        area -= anel[j][0] * anel[i][1]
    return abs(area) / 2.0


def calcular_perimetro(coords: List[Coord2D]) -> float:
    """
    Calcula o perímetro (ou comprimento) somando a distância
    euclidiana entre pontos consecutivos.
    """
    total = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i + 1][0] - coords[i][0]
        dy = coords[i + 1][1] - coords[i][1]
        total += math.sqrt(dx ** 2 + dy ** 2)
    return total


# ── Processadores de geometria GeoJSON ──────────────────────────────────────

def processar_linestring(coords_brutas: list) -> dict:
    """
    Processa uma LineString.
    Se estiver fechada → calcula área e perímetro (polígono implícito).
    Se estiver aberta  → calcula apenas comprimento.
    """
    coords = remover_z(coords_brutas)

    if esta_fechada(coords):
        area = calcular_area(coords)
        perimetro = calcular_perimetro(coords)
        return {
            "interpretacao": "Polígono (LineString fechada)",
            "area_m2": round(area, 4),
            "perimetro_m": round(perimetro, 4),
        }
    else:
        comprimento = calcular_perimetro(coords)
        return {
            "interpretacao": "Linha aberta",
            "comprimento_m": round(comprimento, 4),
        }


def processar_polygon(aneis_brutos: list) -> dict:
    """
    Processa um Polygon GeoJSON.
    Primeiro anel = contorno externo; demais = buracos (subtraídos da área).
    """
    anel_externo = remover_z(aneis_brutos[0])
    area = calcular_area(anel_externo)
    perimetro = calcular_perimetro(anel_externo)

    for buraco in aneis_brutos[1:]:
        area -= calcular_area(remover_z(buraco))

    return {
        "interpretacao": "Polígono",
        "area_m2": round(area, 4),
        "perimetro_m": round(perimetro, 4),
    }


def processar_multilinestring(lista_coords: list) -> dict:
    """Processa um MultiLineString, calculando cada parte individualmente."""
    partes = []
    area_total = 0.0
    perimetro_total = 0.0
    comprimento_total = 0.0

    for i, coords_brutas in enumerate(lista_coords):
        parte = processar_linestring(coords_brutas)
        parte["parte"] = i + 1
        partes.append(parte)
        area_total += parte.get("area_m2", 0)
        perimetro_total += parte.get("perimetro_m", 0)
        comprimento_total += parte.get("comprimento_m", 0)

    return {
        "interpretacao": "MultiLineString",
        "area_total_m2": round(area_total, 4),
        "perimetro_total_m": round(perimetro_total, 4),
        "comprimento_total_m": round(comprimento_total, 4),
        "partes": partes,
    }


# ── Dispatcher de processadores ─────────────────────────────────────────────

PROCESSADORES = {
    "LineString": processar_linestring,
    "Polygon": processar_polygon,
    "MultiLineString": processar_multilinestring,
    # "Point" é ignorado intencionalmente
}
