"""
state_descritivo.py
====================
Estado compartilhado do grafo LangGraph para o Memorial Descritivo.

Todas as informações passam entre os 4 nós via este TypedDict.
Cada nó lê o que precisa e retorna as chaves que modifica.
"""

from typing import TypedDict, Optional, List


class DescritivoState(TypedDict):
    """Estado global do pipeline LangGraph — Memorial Descritivo."""

    # ── Nó 1: Input & Cadastro ──────────────────────────────────────────
    caminho_dxf: str                        # Caminho absoluto do arquivo .DXF temporário
    projeto_id: Optional[int]               # FK para modelo Projeto no Django
    metadados_obra: dict                    # {nome, localizacao, tipo_construcao, padrao_acabamento}

    # ── Nó 2: Extração Estruturada Manual (ezdxf) ───────────────────────
    extracao_bruta: dict                    # JSON completo (dataclass → dict) do dxf_core.extrair_dxf()
    ambientes: List[dict]                   # Ambientes detectados via MTEXT (nome, área, perímetro, pé-direito)
    textos_legenda: List[dict]              # Textos descritivos encontrados {texto, layer}
    resumo_por_camada: dict                 # Resumo por layer {camada: {qtd, area, perimetro, comprimento, volume}}
    estatisticas: dict                      # {total_entidades, total_ignoradas, total_camadas, total_ambientes}

    # ── Nó 3: Agente LLM Auditor ────────────────────────────────────────
    memorial_descritivo: dict               # JSON estruturado do Memorial Descritivo gerado pela LLM
    inconsistencias: List[str]              # Alertas de auditoria identificados pela LLM
    confianca_analise: str                  # "alta" | "media" | "baixa"

    # ── Nó 4: Persistência & Exportação ─────────────────────────────────
    memorial_db_id: Optional[int]           # PK do registro Memorial salvo no banco
    pdf_path: Optional[str]                 # Caminho absoluto do PDF gerado
    exportacao_ok: bool                     # True se salvamento + PDF foram bem-sucedidos

    # ── Controle ────────────────────────────────────────────────────────
    erro: Optional[str]                     # Mensagem de erro (None se tudo OK)
    etapa_atual: str                        # Identificador da etapa corrente
