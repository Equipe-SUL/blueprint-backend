
"""
structural_analysis.py
=====================
Análise geométrica de DXF estrutural:
- Segmenta o ModelSpace em vistas (planos/ cortes/ detalhes)
- Calcula quantidades reais por vista
- Estima volumes com base em seções típicas
- Filtra ruído (hachuras, texto, cotas)
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import math


@dataclass
class ViewInfo:
    """Uma vista dentro do DXF (planta, corte, detalhe)"""
    name: str
    x_min: float
    x_max: float
    entities: List = field(default_factory=list)
    categories: Dict[str, List] = field(default_factory=lambda: {
        "pilar": [], "viga": [], "estaca": [], "laje": [], "fundacao": [],
        "outros": [],
    })


class StructuralAnalyzer:
    """
    Analisa entidades do DXF para extrair quantidades estruturais reais.
    
    Funciona com 2 tipos de layout:
    - Arquitetônico: vistas empilhadas no eixo Y (plantas, cortes)
    - Estrutural: vistas lado a lado no eixo X (locação, forma, detalhes)
    
    Regras de deduplicação:
    - PILARES = max entre vistas (mesmos pilares em todos pavimentos)
    - VIGAS = soma entre vistas (cada pavimento tem seu conjunto)
    - ESTACAS = max entre vistas (fundação única)
    - LAJES = soma entre vistas (cada pavimento)
    """

    GAP_THRESHOLD = 3.0  # gap minimo entre entidades para considerar separacao
    MIN_VIEW_SIZE = 3.0  # tamanho minimo de uma vista
    HISTOGRAM_BINS = 20  # numero de bins para deteccao de clusters por densidade

    # Categorias que se repetem entre pavimentos (max, não soma)
    CAT_DEDUP_MAX = {"pilar", "estaca", "fundacao"}
    # Categorias diferentes por pavimento (soma)
    CAT_DEDUP_SUM = {"viga", "laje"}

    def __init__(self, entities: List[Dict]):
        self.raw_entities = entities
        self.views: List[ViewInfo] = []
        self._analyze()

    def _get_centroid_x(self, entity: Dict) -> float:
        """Obtem centro X da entidade"""
        bbox = entity.get('bbox', {})
        if bbox:
            return (bbox.get('xmin', 0) + bbox.get('xmax', 0)) / 2
        centro = entity.get('centro', (0, 0))
        return centro[0] if isinstance(centro, (tuple, list)) else 0

    def _get_centroid_y(self, entity: Dict) -> float:
        centro = entity.get('centro', (0, 0))
        return centro[1] if isinstance(centro, (tuple, list)) else 0

    def _detect_views(self) -> List[ViewInfo]:
        """
        Segmenta o ModelSpace em vistas usando histograma de densidade X.
        Projetos estruturais brasileiros colocam as vistas lado a lado no eixo X.
        """
        if not self.raw_entities:
            return []

        # Coleta todos os centros X das entidades estruturais
        xs = []
        for e in self.raw_entities:
            cat = self._classify_entity(e)
            if cat != 'outros':
                cx = self._get_centroid_x(e)
                xs.append(cx)

        if not xs:
            return [ViewInfo(name="Unica", x_min=0, x_max=0)]

        x_min, x_max = min(xs), max(xs)
        x_range = x_max - x_min
        if x_range < self.MIN_VIEW_SIZE * 2:
            return [ViewInfo(name="Unica", x_min=x_min, x_max=x_max)]

        # Histograma para detectar clusters
        bin_w = x_range / self.HISTOGRAM_BINS
        bins = [0] * self.HISTOGRAM_BINS
        for x in xs:
            idx = min(int((x - x_min) / bin_w), self.HISTOGRAM_BINS - 1)
            bins[idx] += 1

        # Encontra bins com densidade muito baixa (vales entre clusters)
        max_density = max(bins) if bins else 1
        valley_threshold = max_density * 0.08  # 8% do pico
        
        # Detecta sequencias de bins contiguos com baixa densidade
        in_valley = False
        split_points = []
        for i, count in enumerate(bins):
            if count <= valley_threshold:
                if not in_valley:
                    in_valley = True
                    valley_start_pct = i / self.HISTOGRAM_BINS
            else:
                if in_valley:
                    in_valley = False
                    valley_end_pct = i / self.HISTOGRAM_BINS
                    # So divide se o vale for significativo (> 5% da largura)
                    if (valley_end_pct - valley_start_pct) > 0.05:
                        split_x = x_min + ((valley_start_pct + valley_end_pct) / 2) * x_range
                        split_points.append(split_x)

        if not split_points:
            return [ViewInfo(name="Unica", x_min=x_min, x_max=x_max)]

        # Cria intervalos de vista
        bounds = [x_min] + split_points + [x_max]
        result = []
        names = ["Locação/Baldrame", "Forma Cobertura", "Detalhe", "Corte"]
        for i in range(len(bounds) - 1):
            bxmin = bounds[i]
            bxmax = bounds[i+1]
            if bxmax - bxmin > self.MIN_VIEW_SIZE:
                name = names[i] if i < len(names) else f"Vista {i+1}"
                result.append(ViewInfo(name=name, x_min=bxmin, x_max=bxmax))

        return result if result else [ViewInfo(name="Unica", x_min=x_min, x_max=x_max)]

    def _classify_entity(self, entity: Dict) -> str:
        """Classifica entidade em categoria estrutural"""
        layer = entity.get('layer', '').upper()
        if 'PILAR' in layer:
            return 'pilar'
        elif 'VIGA' in layer:
            return 'viga'
        elif 'ESTACA' in layer:
            return 'estaca'
        elif 'LAJE' in layer:
            return 'laje'
        elif 'FUNDACAO' in layer or 'SAPATA' in layer:
            return 'fundacao'
        return 'outros'

    def _is_structural_entity(self, entity: Dict) -> bool:
        cat = self._classify_entity(entity)
        if cat != 'outros':
            return True
        dtype = entity.get('type', '')
        if dtype in ('TEXT', 'MTEXT', 'DIMENSION', 'HATCH'):
            return False
        return False

    def _assign_to_view(self, entity: Dict, views: List[ViewInfo]):
        """Atribui entidade a vista baseado no centro X"""
        cx = self._get_centroid_x(entity)
        for view in views:
            if view.x_min <= cx <= view.x_max:
                view.entities.append(entity)
                cat = self._classify_entity(entity)
                if cat in view.categories:
                    view.categories[cat].append(entity)
                return
        # Mais proxima
        if views:
            best = min(views, key=lambda v: abs((v.x_min + v.x_max)/2 - cx))
            best.entities.append(entity)
            cat = self._classify_entity(entity)
            if cat in best.categories:
                best.categories[cat].append(entity)

    def _compute_view_stats(self, view: ViewInfo) -> Dict:
        """Calcula metricas agregadas por vista"""
        stats = {}
        for cat_name, entities in view.categories.items():
            if not entities:
                continue

            if cat_name == 'pilar':
                closed = [e for e in entities if e.get('closed', False) or e.get('type') == 'CIRCLE']
                count = len(closed)
                area = sum(e.get('area_m2', 0) for e in closed) if closed else 0
                if count > 0:
                    stats[cat_name] = {"count": count, "area_m2": round(area, 3), "unit": "m2"}

            elif cat_name == 'estaca':
                closed = [e for e in entities if e.get('closed', False) or e.get('type') == 'CIRCLE']
                count = len(closed)
                area = sum(e.get('area_m2', 0) for e in closed) if closed else 0
                # Se nao achou fechadas, usa todas
                if count == 0:
                    area = sum(e.get('area_m2', 0) for e in entities)
                    count = len(entities)
                if count > 0:
                    stats[cat_name] = {"count": count, "area_m2": round(area, 3), "unit": "m2"}

            elif cat_name == 'viga':
                comp = sum(e.get('comprimento_m', 0) for e in entities)
                if comp > 0:
                    stats[cat_name] = {"comprimento_m": round(comp, 2), "unit": "m"}

            elif cat_name == 'laje':
                area = sum(e.get('area_m2', 0) for e in entities if e.get('area_m2', 0) > 0)
                if area > 0:
                    stats[cat_name] = {"area_m2": round(area, 2), "unit": "m2"}

        return stats

    def _analyze(self):
        self.views = self._detect_views()
        # Itera sobre copia para evitar loop infinito se assign_to_view modificar a lista
        for entity in list(self.raw_entities):
            if self._is_structural_entity(entity):
                self._assign_to_view(entity, self.views)

    def get_deduplicated_quantities(self) -> Dict:
        """
        Retorna quantidades deduplicadas.
        - CAT_DEDUP_MAX: pega o max entre vistas (mesmo elemento em multiplos pavimentos)
        - CAT_DEDUP_SUM: soma entre vistas (cada pavimento tem seus proprios elementos)
        """
        if not self.views:
            return {}

        all_stats = [self._compute_view_stats(v) for v in self.views]
        categories = set()
        for s in all_stats:
            categories.update(s.keys())

        result = {}
        for cat in sorted(categories):
            values = [s.get(cat, {}) for s in all_stats if cat in s]
            if not values:
                continue

            if cat in self.CAT_DEDUP_MAX:
                # Pega o maior valor (vista mais completa)
                if "count" in values[0]:
                    best = max(values, key=lambda v: v.get("count", 0))
                    result[cat] = dict(best)
                elif "comprimento_m" in values[0]:
                    best = max(values, key=lambda v: v.get("comprimento_m", 0))
                    result[cat] = dict(best)

            elif cat in self.CAT_DEDUP_SUM:
                # Soma entre vistas
                if "comprimento_m" in values[0]:
                    total = sum(v.get("comprimento_m", 0) for v in values)
                    result[cat] = {"comprimento_m": round(total, 2), "unit": "m"}
                elif "area_m2" in values[0]:
                    total = sum(v.get("area_m2", 0) for v in values)
                    result[cat] = {"area_m2": round(total, 2), "unit": "m2"}

        return result

    def estimate_volumes(self, quantities: Dict,
                         pe_direito: float = 3.0,
                         estaca_profundidade: float = 10.0) -> Dict:
        """
        Estima volumes reais a partir das quantidades geometricas.
        """
        result = {}

        for cat, data in quantities.items():
            if cat == "pilar":
                count = data.get("count", 0)
                area_secao = data.get("area_m2", 0)
                if area_secao > 0:
                    area_por_pilar = area_secao / count if count > 0 else area_secao
                    vol_total = area_por_pilar * pe_direito * count
                    result[cat] = {
                        "count": count,
                        "area_secao_m2": round(area_secao, 3),
                        "volume_m3": round(vol_total, 2),
                        "preco_unit": 1000.00,
                    }

            elif cat == "viga":
                comp = data.get("comprimento_m", 0)
                SECAO_VIGA = 0.06  # 0.15 x 0.40 m
                result[cat] = {
                    "comprimento_m": comp,
                    "secao_m2": SECAO_VIGA,
                    "volume_m3": round(comp * SECAO_VIGA, 2),
                    "preco_unit": 950.00,
                }

            elif cat == "estaca":
                count = data.get("count", 0)
                area_secao = data.get("area_m2", 0)
                if area_secao > 0 and count > 0:
                    area_por_estaca = area_secao / count
                    vol_total = area_por_estaca * estaca_profundidade * count
                    result[cat] = {
                        "count": count,
                        "area_secao_m2": round(area_secao, 3),
                        "volume_m3": round(vol_total, 2),
                        "preco_unit": 650.00,
                    }

            elif cat == "laje":
                area = data.get("area_m2", 0)
                result[cat] = {
                    "area_m2": area,
                    "espessura_m": 0.12,
                    "volume_m3": round(area * 0.12, 2),
                    "preco_unit": 130.00,
                }

        return result


# ─── Função de integração com o pipeline ───────────────────────────────

CAMADAS_ESTRUTURAIS = {"PILAR", "VIGA", "VIGAS", "ESTACA", "LAJE", "FUNDACAO",
                       "SAPATA", "BALDAME", "FORMA", "LOCACAO"}


def detectar_estrutural(entidades: list) -> bool:
    """Verifica se o DXF contém camadas estruturais."""
    for e in entidades:
        layer = getattr(e, 'camada', e.get('layer', '')) if isinstance(e, dict) else getattr(e, 'camada', '')
        for nome in CAMADAS_ESTRUTURAIS:
            if nome in layer.upper():
                return True
    return False


def entidades_para_dicts(entidades: list) -> list:
    """Converte entidades do MemorialCalculo para dicts que o StructuralAnalyzer entende."""
    result = []
    for e in entidades:
        if isinstance(e, dict):
            result.append(e)
            continue
        cx = e.centro[0] if e.centro else 0
        cy = e.centro[1] if e.centro else 0
        size = max(e.comprimento_m, math.sqrt(e.area_m2) if e.area_m2 > 0 else 1.0, 0.5)
        result.append({
            'layer': e.camada,
            'type': e.tipo_entidade,
            'comprimento_m': e.comprimento_m,
            'area_m2': e.area_m2,
            'closed': e.fechada,
            'centro': (cx, cy),
            'bbox': {'xmin': cx - size / 2, 'xmax': cx + size / 2,
                     'ymin': cy - size / 2, 'ymax': cy + size / 2},
        })
    return result


def adaptar_analise_estrutural(memorial) -> list:
    """
    Analisa entidades do DXF estrutural e retorna itens no formato do adapter.
    
    Args:
        memorial: MemorialCalculo de extrair_dxf()
    
    Returns:
        Lista de itens no formato: {id, type, quantity, description, unidade}
        Vazia se o DXF não tiver camadas estruturais.
    """
    if not detectar_estrutural(memorial.entidades):
        return []

    dicts = entidades_para_dicts(memorial.entidades)
    analyzer = StructuralAnalyzer(dicts)
    quantities = analyzer.get_deduplicated_quantities()
    if not quantities:
        return []

    volumes = analyzer.estimate_volumes(quantities)

    NOME_DESC = {
        "pilar": "Pilar de concreto armado",
        "viga": "Viga de concreto armado",
        "estaca": "Estaca de concreto armado",
        "laje": "Laje de concreto armado",
        "fundacao": "Fundação de concreto armado",
    }

    items = []
    for cat, data in sorted(volumes.items()):
        vol = data.get("volume_m3", 0)
        if vol <= 0:
            continue
        count = data.get("count", 0)
        comp = data.get("comprimento_m", 0)

        if cat in ("estaca",):
            items.append({
                "id": f"ESTR_{cat.upper()}_001",
                "type": cat,
                "quantity": round(count, 0),
                "description": NOME_DESC.get(cat, cat),
                "unidade": "un",
                "quantidade_elementos": int(count),
            })
        else:
            items.append({
                "id": f"ESTR_{cat.upper()}_001",
                "type": cat,
                "quantity": round(vol, 2),
                "description": NOME_DESC.get(cat, cat),
                "unidade": "m3",
                "quantidade_elementos": int(count or comp),
            })

    return items
