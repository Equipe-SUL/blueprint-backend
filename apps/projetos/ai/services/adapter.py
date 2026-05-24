"""
adapter.py
==========
Adaptador que transforma o JSON do memorial de c├ílculo (Etapa 1)
no formato esperado pelo orcamento_service (Etapa 2).

Garante o contrato de dados entre as duas etapas do sistema.
"""

from typing import List, Dict


# Mapeamento: Camada DXF ÔåÆ (type, description para busca SINAPI, campo de quantidade, unidade)
MAPA_CAMADAS = {
    "PILAR":    {"type": "pilar",    "description": "Pilar de concreto armado",    "campo_qty": "volume_m3",       "unidade": "m3"},
    "VIGA":     {"type": "viga",     "description": "Viga de concreto armado",     "campo_qty": "volume_m3",       "unidade": "m3"},
    "VIGAS":    {"type": "viga",     "description": "Viga de concreto armado",     "campo_qty": "volume_m3",       "unidade": "m3"},
    "ESTACA":   {"type": "estaca",   "description": "Estaca de concreto armado",   "campo_qty": "volume_m3",       "unidade": "m3"},
    "LAJE":     {"type": "laje",     "description": "Laje de concreto armado",     "campo_qty": "area_total_m2",   "unidade": "m2"},
    "FUNDACAO": {"type": "fundacao", "description": "Fundacao de concreto armado", "campo_qty": "volume_m3",       "unidade": "m3"},
    "PAREDE":   {"type": "parede",   "description": "Alvenaria de vedacao",        "campo_qty": "area_total_m2",   "unidade": "m2"},
    "PAREDE-HACH": {"type": "parede", "description": "Alvenaria de vedacao",       "campo_qty": "area_total_m2",   "unidade": "m2"},
    "ESQUADRIA": {"type": "esquadria", "description": "Esquadrias de aluminio ou madeira", "campo_qty": "comprimento_total_m", "unidade": "m"},
    "PISO":     {"type": "piso",     "description": "Piso ceramico ou porcelanato", "campo_qty": "area_total_m2",   "unidade": "m2"},
    "EQUIPAMENTOS": {"type": "equipamentos", "description": "Equipamentos e mobilia", "campo_qty": "area_total_m2",   "unidade": "m2"},
    "HACH":     {"type": "hachura",  "description": "Hachura de parede ou piso",   "campo_qty": "area_total_m2",   "unidade": "m2"},
}


def adaptar_memorial_para_orcamento(relatorio_etapa1: dict) -> List[Dict]:
    """
    Transforma o JSON do memorial de c├ílculo (Etapa 1)
    no formato esperado pelo orcamento_service (Etapa 2).

    Entrada (Etapa 1 - resumo_por_camada):
        {
            "PILAR": {"quantidade": 12, "area_m2": 3.6, "perimetro_m": 24.0, "comprimento_m": 0},
            "VIGA":  {"quantidade": 8,  "area_m2": 0,   "perimetro_m": 0,    "comprimento_m": 45.2}
        }

    Sa├¡da (Etapa 2 - formato esperado):
        [
            {"id": "PILAR_001", "type": "pilar", "quantity": 3.6, "description": "Pilar de concreto armado", ...},
            {"id": "VIGA_002",  "type": "viga",  "quantity": 45.2, "description": "Viga de concreto armado", ...}
        ]
    """
    resumo = relatorio_etapa1.get("resumo_por_camada", {})
    itens_adaptados = []

    for idx, (camada, dados) in enumerate(resumo.items(), start=1):
        # Ignora camadas de anotação/detalhe/desenho (não são itens construtivos)
        camada_upper = camada.upper()
        if any(camada_upper.startswith(p) for p in ("DETALHE_", "TEXTO", "TXT_", "COTA", "CARIMBO", "PROV", "DIVERSOS", "PROJECAO")):
            continue

        config = MAPA_CAMADAS.get(camada_upper, None)

        if config:
            tipo = config["type"]
            descricao = config["description"]
            campo_qty = config["campo_qty"]
            unidade = config["unidade"]
            quantidade = dados.get(campo_qty, 0)
            if quantidade == 0:
                area = dados.get("area_total_m2", 0) or dados.get("area_m2", 0)
                comp = dados.get("comprimento_total_m", 0) or dados.get("comprimento_m", 0)
                if area > 0:
                    unidade = "m2"
                    quantidade = area
                elif comp > 0:
                    unidade = "m"
                    quantidade = comp
        else:
            # Camada desconhecida: gera descricao mais rica para busca SINAPI
            tipo = camada.lower()
            nome_limpo = camada.replace("_", " ").replace("-", " ").strip().title()
            descricao = f"{nome_limpo}"
            # Tenta area_total_m2, comprimento_total_m; fallback para keys sem _total_
            area = dados.get("area_total_m2", 0) or dados.get("area_m2", 0)
            comp = dados.get("comprimento_total_m", 0) or dados.get("comprimento_m", 0)
            if area > 0:
                unidade = "m2"
                quantidade = area
            elif comp > 0:
                unidade = "m"
                quantidade = comp
            else:
                quantidade = 0
                unidade = "m"

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


# Mapeamento de blocos CAD -> descricao legivel para SINAPI
# Usa startswith() para matching parcial, entao a ordem importa
# (mais especificos primeiro)
MAPA_BLOCOS = {
    # Blocos ADC (projeto geminado)
    "PORTA80":          ("esquadria", "Porta de madeira 0.80x2.10",               "un"),
    "PORTA70":          ("esquadria", "Porta de madeira 0.70x2.10",               "un"),
    "ADC_WC_BACIA":     ("louca",     "Bacia sanitaria com caixa acoplada",       "un"),
    "ADC_WC_LAV":       ("louca",     "Lavatorio com cuba de embutir",            "un"),
    "ADC_COZ_PIA":      ("louca",     "Pia de cozinha 120x55cm aco inox",        "un"),
    "ADC_CHUVEIRO":     ("metais",    "Chuveiro eletrico",                        "un"),
    "BOX-BANHO":        ("metais",    "Box de banho 80cm",                        "un"),
    "ADC_TANQUE":       ("equip",     "Tanque de lavar 50x50cm",                  "un"),
    "ADC_MOB_LAVR":     ("equip",     "Maquina de lavar 10kg",                    "un"),
    "ADC_MOB_FOG":      ("equip",     "Fogao 4 bocas",                            "un"),
    "ADC_TORN":         ("metais",    "Torneira de cozinha",                      "un"),
    "ADC_MCOZ":         ("louca",     "Movel de cozinha",                         "un"),
    # Blocos casona
    "CAMAC":            ("equip",     "Cama de casal com colchao",                "un"),
    "CAMAS":            ("equip",     "Cama de solteiro com colchao",             "un"),
    "BACIA":            ("louca",     "Bacia sanitaria com caixa acoplada",       "un"),
    "CHUVEIRO":         ("metais",    "Chuveiro eletrico",                        "un"),
    "CUBA":             ("louca",     "Cuba de embutir para lavatorio",           "un"),
    "GELAD":            ("equip",     "Geladeira/Refrigerador",                   "un"),
    "SOFA3":            ("equip",     "Sofa 3 lugares estofado",                  "un"),
    "SOFA2":            ("equip",     "Sofa 2 lugares estofado",                  "un"),
    "TV":               ("equip",     "Televisao",                                "un"),
    "MESA8C":           ("equip",     "Mesa com 8 cadeiras",                      "un"),
    "VEG1":             ("equip",     "Vaso de planta ornamental",                "un"),
}


def adaptar_blocos_para_orcamento(full_report: dict) -> List[Dict]:
    """
    Converte blocos do CAD engine (full_report.blocos_por_tipo)
    em itens para orcamento SINAPI.

    Entrada: {"PORTA80": 9, "ADC_WC_BACIA_01-P": 3, ...}
    Saida:   [{"id": "PORTA80", "type": "esquadria", "description": "Porta...", "quantity": 9, "unidade": "un"}, ...]
    """
    blocos_por_tipo = full_report.get("blocos_por_tipo", {})
    itens = []
    idx = 0

    for nome_bloco, quantidade in blocos_por_tipo.items():
        if nome_bloco.startswith("*"):
            continue  # blocos anonimos

        qtd = int(quantidade) if isinstance(quantidade, (int, float)) else 1

        # Procura matching parcial no mapa (ex: ADC_WC_BACIA_01-P -> ADC_WC_BACIA)
        tipo, descricao, unidade = "bloco", f"Bloco: {nome_bloco}", "un"
        for chave, (t, d, u) in MAPA_BLOCOS.items():
            if nome_bloco.upper().startswith(chave):
                tipo, descricao, unidade = t, d, u
                break

        idx += 1
        itens.append({
            "id": f"{nome_bloco}_{idx:03d}",
            "type": tipo,
            "description": descricao,
            "quantity": qtd,
            "unidade": unidade,
            "quantidade_elementos": qtd,
        })

    return itens
