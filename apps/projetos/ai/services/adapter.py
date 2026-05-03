"""
adapter.py
==========
Adaptador que transforma o JSON do memorial de cálculo (Etapa 1)
no formato esperado pelo orcamento_service (Etapa 2).

Garante o contrato de dados entre as duas etapas do sistema.
"""

from typing import List, Dict


# Mapeamento: Camada DXF → (type, description para busca SINAPI, campo de quantidade, unidade)
MAPA_CAMADAS = {
    "PILAR":    {"type": "pilar",    "description": "Pilar de concreto armado",    "campo_qty": "area_m2",       "unidade": "m2"},
    "VIGA":     {"type": "viga",     "description": "Viga de concreto armado",     "campo_qty": "comprimento_m", "unidade": "m"},
    "ESTACA":   {"type": "estaca",   "description": "Estaca de concreto armado",   "campo_qty": "area_m2",       "unidade": "m2"},
    "LAJE":     {"type": "laje",     "description": "Laje de concreto armado",     "campo_qty": "area_m2",       "unidade": "m2"},
    "FUNDACAO": {"type": "fundacao", "description": "Fundação de concreto armado", "campo_qty": "area_m2",       "unidade": "m2"},
    "PAREDE":   {"type": "parede",   "description": "Alvenaria de vedação",        "campo_qty": "area_m2",       "unidade": "m2"},
}


def adaptar_memorial_para_orcamento(relatorio_etapa1: dict) -> List[Dict]:
    """
    Transforma o JSON do memorial de cálculo (Etapa 1)
    no formato esperado pelo orcamento_service (Etapa 2).

    Entrada (Etapa 1 - resumo_por_camada):
        {
            "PILAR": {"quantidade": 12, "area_m2": 3.6, "perimetro_m": 24.0, "comprimento_m": 0},
            "VIGA":  {"quantidade": 8,  "area_m2": 0,   "perimetro_m": 0,    "comprimento_m": 45.2}
        }

    Saída (Etapa 2 - formato esperado):
        [
            {"id": "PILAR_001", "type": "pilar", "quantity": 3.6, "description": "Pilar de concreto armado", ...},
            {"id": "VIGA_002",  "type": "viga",  "quantity": 45.2, "description": "Viga de concreto armado", ...}
        ]
    """
    resumo = relatorio_etapa1.get("resumo_por_camada", {})
    itens_adaptados = []

    for idx, (camada, dados) in enumerate(resumo.items(), start=1):
        config = MAPA_CAMADAS.get(camada.upper(), None)

        if config:
            tipo = config["type"]
            descricao = config["description"]
            campo_qty = config["campo_qty"]
            unidade = config["unidade"]
            quantidade = dados.get(campo_qty, 0)
        else:
            # Camada desconhecida: usa o melhor valor disponível
            tipo = camada.lower()
            descricao = f"Elemento estrutural: {camada}"
            unidade = "m2" if dados.get("area_m2", 0) > 0 else "m"
            quantidade = dados.get("area_m2", 0) or dados.get("comprimento_m", 0)

        # Ignora camadas sem quantidades reais
        if quantidade == 0:
            continue

        itens_adaptados.append({
            "id": f"{camada}_{idx:03d}",
            "type": tipo,
            "quantity": round(quantidade, 2),
            "description": descricao,
            "unidade": unidade,
            "quantidade_elementos": dados.get("quantidade", 0),
        })

    return itens_adaptados
