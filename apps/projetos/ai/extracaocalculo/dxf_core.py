"""
dxf_core.py
===========
Módulo central de extração direta de dados de arquivos .dxf usando ezdxf.
Filosofia: IA faz o mínimo — tudo é extraído por mapeamento estático de layers.
Sem dependência de Django, GeoJSON ou vectorstore.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

# ── Mapeamento estático de layers ─────────────────────────────────────────────
MAP_LAYER = {
    "ARQ - ALVENARIA ALTA": "parede",
    "ARQUITETÔNICO - ALVENARIA ALTA": "parede",
    "ARQ - ALVENARIA MÉDIA-BAIXA": "parede",
    "ARQ - ALVENARIA (-)": "parede",
    "ARQ - DRY-WALL": "parede_leve",
    "ARQ - ESQUADRIAS": "vao",
    "ESQUADRIAS": "vao",
    "ARQ - TEXTOS": "texto",
    "ARQUITETÔNICO - TEXTOS": "texto",
    "ARQ - COBERTURA": "cobertura",
    "PAREDE": "parede",
    "PILAR": "pilar",
    "ESTRUTURAL - PILARES": "pilar",
    "VIGA": "viga",
    "ESTRUTURAL - VIGAS": "viga",
    "LAJE": "laje",
    "ESTRUTURAL - LAJES": "laje",
    "ESTACA": "estaca",
    "FUNDACAO": "fundacao",
    "HIDROSSANITÁRIO - ÁGUA FRIA": "hidro",
    "HIDROSSANITÁRIO - ESGOTO": "hidro",
    "HIDROSSANITÁRIO - VENTILAÇÃO": "hidro",
    "DEFPOINTS": "ignorar",
    "0": "ignorar",
    "COTAS": "ignorar",
    "CARIMBO": "ignorar",
    "TEXTOS": "ignorar",
    "PROJEÇÃO": "ignorar",
}

LAYER_SUBSTRING = {
    "ALVENARIA": "parede",
    "ESQUADRIA": "vao",
    "PILAR": "pilar",
    "VIGA": "viga",
    "LAJE": "laje",
    "ESTACA": "estaca",
    "HIDRO": "hidro",
    "COBERTURA": "cobertura",
    "ELÉTRICA": "eletrica",
    "CIRCUITO": "eletrica",
    "DRY-WALL": "parede_leve",
    "COTA": "ignorar",
    "DESNÍVEL": "ignorar",
    "PROJEÇ": "ignorar",
}

ESPESSURA_PADRAO = {
    "parede": 0.15,
    "pilar": 0.20,
    "viga": 0.20,
    "laje": 0.12,
    "estaca": 0.30,
    "fundacao": 0.30,
    "parede_leve": 0.10,
}

ALTURA_PADRAO = 3.0
ALTURA_VAO = 2.1

@dataclass
class EntidadeExtraida:
    indice: int
    tipo_entidade: str
    camada: str
    categoria: str
    handle: str = ""
    fechada: bool = False
    comprimento_m: float = 0.0
    area_m2: float = 0.0
    perimetro_m: float = 0.0
    centro: Tuple[float, float] = (0.0, 0.0)

@dataclass
class ResumoCamada:
    camada: str
    categoria: str
    quantidade: int = 0
    area_total_m2: float = 0.0
    perimetro_total_m: float = 0.0
    comprimento_total_m: float = 0.0
    volume_m3: float = 0.0
    area_liquida_m2: float = 0.0

@dataclass
class AmbienteTexto:
    nome: str
    area_m2: float = 0.0
    perimetro_m: float = 0.0
    pe_direito_m: float = 0.0

@dataclass
class MemorialCalculo:
    arquivo_origem: str
    total_entidades: int = 0
    total_ignoradas: int = 0
    entidades: List[EntidadeExtraida] = field(default_factory=list)
    resumo_por_camada: Dict[str, ResumoCamada] = field(default_factory=dict)
    ambientes: List[AmbienteTexto] = field(default_factory=list)
    textos_legenda: List[dict] = field(default_factory=list)

def _dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def _comprimento_pontos(coords):
    return sum(_dist(coords[i], coords[i+1]) for i in range(len(coords)-1))

def _area_shoelace(coords):
    n = len(coords)
    if n < 3: return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2.0

def _esta_fechada(coords):
    if len(coords) < 3: return False
    return _dist(coords[0], coords[-1]) < 1e-6

def _centro_pontos(coords):
    if not coords: return (0.0, 0.0)
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return (sum(xs)/len(xs), sum(ys)/len(ys))

def classificar_layer(layer_name: str) -> str:
    upper = layer_name.upper().strip()
    if upper in MAP_LAYER: return MAP_LAYER[upper]
    for substr, cat in LAYER_SUBSTRING.items():
        if substr in upper: return cat
    return "outro"

def _processar_line(entity) -> Optional[EntidadeExtraida]:
    p1 = (entity.dxf.start.x, entity.dxf.start.y)
    p2 = (entity.dxf.end.x, entity.dxf.end.y)
    comp = _dist(p1, p2)
    centro = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
    return EntidadeExtraida(0, "LINE", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, False, round(comp, 4), 0.0, 0.0, centro)

def _processar_lwpolyline(entity) -> Optional[EntidadeExtraida]:
    coords = [(p[0], p[1]) for p in entity.get_points("xy")]
    if len(coords) < 2: return None
    fechada = entity.is_closed or _esta_fechada(coords)
    comp = _comprimento_pontos(coords)
    area = _area_shoelace(coords) if fechada else 0.0
    return EntidadeExtraida(0, "LWPOLYLINE", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, fechada, round(comp, 4), round(area, 4),
                            round(comp, 4) if fechada else 0.0, _centro_pontos(coords))

def _processar_polyline(entity) -> Optional[EntidadeExtraida]:
    try: coords = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    except: return None
    if len(coords) < 2: return None
    fechada = bool(entity.dxf.flags & 1)
    comp = _comprimento_pontos(coords)
    area = _area_shoelace(coords) if fechada else 0.0
    return EntidadeExtraida(0, "POLYLINE", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, fechada, round(comp, 4), round(area, 4),
                            round(comp, 4) if fechada else 0.0, _centro_pontos(coords))

def _processar_arc(entity) -> Optional[EntidadeExtraida]:
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    raio = entity.dxf.radius
    ang = math.radians(entity.dxf.end_angle - entity.dxf.start_angle)
    if ang < 0: ang += 2 * math.pi
    comp = raio * ang
    return EntidadeExtraida(0, "ARC", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, False, round(comp, 4), 0.0, 0.0, (cx, cy))

def _processar_circle(entity) -> Optional[EntidadeExtraida]:
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    raio = entity.dxf.radius
    area = math.pi * raio ** 2
    perim = 2 * math.pi * raio
    return EntidadeExtraida(0, "CIRCLE", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, True, 0.0, round(area, 4), round(perim, 4), (cx, cy))

def _processar_spline(entity) -> Optional[EntidadeExtraida]:
    try: coords = [(p[0], p[1]) for p in entity.control_points]
    except: return None
    if len(coords) < 2: return None
    comp = _comprimento_pontos(coords)
    return EntidadeExtraida(0, "SPLINE", entity.dxf.layer, classificar_layer(entity.dxf.layer),
                            entity.dxf.handle, False, round(comp, 4), 0.0, 0.0, _centro_pontos(coords))

PROCESSADORES = {
    "LINE": _processar_line,
    "LWPOLYLINE": _processar_lwpolyline,
    "POLYLINE": _processar_polyline,
    "ARC": _processar_arc,
    "CIRCLE": _processar_circle,
    "SPLINE": _processar_spline,
}

def _parse_ambiente_mtext(texto_bruto: str) -> Optional[AmbienteTexto]:
    if 'm²' not in texto_bruto or 'P=' not in texto_bruto: return None
    linhas = texto_bruto.split('\\P')
    try:
        nome = re.sub(r'\\[a-zA-Z0-9.]+;', '', linhas[0]).strip()
        area = float(re.search(r'([\d,]+)m²', linhas[1]).group(1).replace(',', '.'))
        perimetro = float(re.search(r'P=([\d,]+)m', linhas[2]).group(1).replace(',', '.'))
        pe_direito = 0.0
        if len(linhas) > 3 and 'PD=' in linhas[3]:
            pe_direito = float(re.search(r'PD=([\d,]+)', linhas[3]).group(1).replace(',', '.'))
        return AmbienteTexto(nome=nome, area_m2=area, perimetro_m=perimetro, pe_direito_m=pe_direito)
    except: return None

def extrair_dxf(caminho_dxf: str) -> MemorialCalculo:
    print(f"\n[LEITURA] Lendo arquivo: {caminho_dxf}")
    doc = ezdxf.readfile(caminho_dxf)
    msp = doc.modelspace()

    memorial = MemorialCalculo(arquivo_origem=caminho_dxf)
    idx = 0
    ignoradas = 0

    for entity in msp:
        tipo = entity.dxftype()

        if tipo in ("TEXT", "MTEXT"):
            texto = entity.dxf.text if tipo == "TEXT" else entity.text
            texto_limpo = re.sub(r'\\[a-zA-Z0-9.]+;', '', texto.replace('\\P', ' ')).strip()
            amb = _parse_ambiente_mtext(texto)
            if amb: memorial.ambientes.append(amb)
            elif len(texto_limpo) > 2:
                memorial.textos_legenda.append({"texto": texto_limpo, "layer": entity.dxf.layer})
            continue

        processador = PROCESSADORES.get(tipo)
        if processador is None:
            ignoradas += 1
            continue

        try: entidade = processador(entity)
        except:
            ignoradas += 1
            continue

        if entidade is None:
            ignoradas += 1
            continue

        if entidade.categoria == "ignorar":
            ignoradas += 1
            continue

        if entidade.categoria in ("pilar", "estaca") and not entidade.fechada and entidade.area_m2 == 0:
            ignoradas += 1
            continue

        idx += 1
        entidade.indice = idx
        memorial.entidades.append(entidade)

    memorial.total_entidades = idx
    memorial.total_ignoradas = ignoradas

    resumo: Dict[str, ResumoCamada] = {}
    for ent in memorial.entidades:
        chave = ent.camada
        if chave not in resumo:
            resumo[chave] = ResumoCamada(camada=chave, categoria=ent.categoria)
        r = resumo[chave]
        r.quantidade += 1
        r.area_total_m2 += ent.area_m2
        r.perimetro_total_m += ent.perimetro_m
        r.comprimento_total_m += ent.comprimento_m

    area_vaos = sum(r.comprimento_total_m * ALTURA_VAO for r in resumo.values() if r.categoria == "vao")

    for chave, r in resumo.items():
        esp = ESPESSURA_PADRAO.get(r.categoria, 0)
        if r.categoria == "parede":
            area_bruta = r.comprimento_total_m * ALTURA_PADRAO
            r.area_total_m2 = round(area_bruta, 4) if r.area_total_m2 == 0 else r.area_total_m2
            r.area_liquida_m2 = round(max(r.area_total_m2 - area_vaos, 0), 4)
            r.volume_m3 = round(r.area_liquida_m2 * esp, 4)
        elif esp > 0:
            r.volume_m3 = round(r.area_total_m2 * esp, 4)

        r.area_total_m2 = round(r.area_total_m2, 4)
        r.perimetro_total_m = round(r.perimetro_total_m, 4)
        r.comprimento_total_m = round(r.comprimento_total_m, 4)

    memorial.resumo_por_camada = resumo
    print(f"[OK] Extracao concluida: {idx} entidades, {ignoradas} ignoradas")
    return memorial
