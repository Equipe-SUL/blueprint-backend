"""
builder_descritivo.py
======================
Monta e compila o grafo LangGraph para o Memorial Descritivo.

Fluxo:
    upload_cadastro → extraction_manual → (dados OK?) → llm_analyst → (análise OK?) → storage_export → END
                                         ↓ (sem dados)                ↓ (erro LLM)
                                         END                         END

O grafo usa checkpointer (MemorySaver) para manter compatibilidade
com o padrão do projeto e possibilitar futuras pausas com interrupt().
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from apps.projetos.ai.grafo_novo.state_descritivo import DescritivoState
from apps.projetos.ai.grafo_novo.nodes_descritivo import (
    node_upload_cadastro,
    node_extraction_manual,
    node_llm_analyst,
    node_storage_export,
)
from apps.projetos.ai.grafo_novo.edges_descritivo import (
    decidir_apos_extracao,
    decidir_apos_analise,
)


def construir_grafo_descritivo():
    """
    Monta o grafo completo do pipeline Memorial Descritivo.

    Fluxo:
        upload_cadastro → extraction_manual →
            ↓ (dados OK) → llm_analyst →
                ↓ (análise OK) → storage_export → END
            ↓ (sem dados) → END
                ↓ (erro) → END

    Retorna:
        CompiledGraph pronto para .invoke()
    """
    g = StateGraph(DescritivoState)

    # ── Nós ──────────────────────────────────────────────────────────────
    g.add_node("upload_cadastro", node_upload_cadastro)
    g.add_node("extraction_manual", node_extraction_manual)
    g.add_node("llm_analyst", node_llm_analyst)
    g.add_node("storage_export", node_storage_export)

    # ── Arestas ──────────────────────────────────────────────────────────
    # Ponto de entrada
    g.set_entry_point("upload_cadastro")

    # upload_cadastro → extraction_manual (sempre)
    g.add_edge("upload_cadastro", "extraction_manual")

    # extraction_manual → (condicional) → llm_analyst OU END
    g.add_conditional_edges("extraction_manual", decidir_apos_extracao, {
        "analise": "llm_analyst",
        "fim_erro": END,
    })

    # llm_analyst → (condicional) → storage_export OU END
    g.add_conditional_edges("llm_analyst", decidir_apos_analise, {
        "exportar": "storage_export",
        "fim_erro": END,
    })

    # storage_export → END (sempre)
    g.add_edge("storage_export", END)

    # ── Compilar com checkpointer ────────────────────────────────────────
    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


# ── Singleton do grafo compilado ─────────────────────────────────────────────
_grafo_descritivo = None


def get_grafo_descritivo():
    """Retorna o grafo descritivo compilado (singleton)."""
    global _grafo_descritivo
    if _grafo_descritivo is None:
        _grafo_descritivo = construir_grafo_descritivo()
    return _grafo_descritivo
