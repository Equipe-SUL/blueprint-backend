"""
state.py
========
Estado compartilhado do grafo LangGraph (BlueprintState).

Todas as informações passam entre os nós via este TypedDict.
Cada nó lê o que precisa e retorna as chaves que modifica.
"""

from typing import TypedDict, Optional, List, Dict


class BlueprintState(TypedDict):
    """Estado global do pipeline LangGraph Blueprint."""

    # ── Entrada ──────────────────────────────────────────────────────────
    caminho_dxf: str
    projeto_id: Optional[int]

    # ── Nó 1 — Extração (determinístico) ────────────────────────────────
    entidades_brutas: List[dict]            # Entidades filtradas do DXF
    layers_encontradas: List[str]           # Layers únicas no arquivo
    estatisticas_extracao: dict             # Contagem por tipo de entidade
    total_ignorados_extracao: int           # Entidades descartadas na extração

    # ── Nó 2 — Classificação (regras + LLM) ─────────────────────────────
    mapa_layers: Dict[str, str]             # {"P-PILAR": "pilar", "0": "desconhecido"}
    layers_ambiguas: List[str]              # Layers não classificadas

    # ── Nó 3 — Filtragem pós-classificação ──────────────────────────────
    entidades_filtradas: List[dict]         # Entidades com categorias descartáveis removidas
    entidades_removidas: int                # Contagem do que foi descartado
    motivos_remocao: dict                   # {"anotacao": 45, "eletrica": 12}

    # ── Nó 4 — Validação ────────────────────────────────────────────────
    validacao_ok: bool
    alertas: List[str]                      # "Pilar com área > 10m² detectado"

    # ── Nó 5 — Cálculo geométrico ──────────────────────────────────────
    memorial_calculo: dict                  # Relatório com áreas, perímetros, resumo

    # ── Nó 6 — Adaptação ───────────────────────────────────────────────
    itens_adaptados: List[dict]             # Formato esperado pelo RAG

    # ── Nó 7 — RAG SINAPI ──────────────────────────────────────────────
    sugestoes_sinapi: List[dict]            # Sugestões de itens SINAPI

    # ── Nó 8 — Avaliação LLM ───────────────────────────────────────────
    # (integrado no RAG por enquanto)

    # ── Nó 9 — Orçamento ───────────────────────────────────────────────
    orcamento_final: dict                   # Orçamento com BDI

    # ── Controle ────────────────────────────────────────────────────────
    erro: Optional[str]
    etapa_atual: str
