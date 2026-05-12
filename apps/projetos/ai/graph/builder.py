"""
builder.py
==========
Monta e compila o grafo LangGraph Blueprint.

O grafo usa checkpointer para suportar human-in-the-loop via interrupt().
Quando o nó de validação detecta alertas críticos, ele chama interrupt()
e o grafo pausa até receber uma resposta humana.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from apps.projetos.ai.graph.state import BlueprintState
from apps.projetos.ai.graph.nodes import (
    node_extrair,
    node_classificar,
    node_filtrar,
    node_validar,
    node_calcular,
    node_adaptar,
    node_rag,
    node_orcamento,
)
from apps.projetos.ai.graph.edges import (
    decidir_apos_validacao,
    decidir_apos_adaptacao,
)


def construir_grafo_blueprint():
    """
    Monta o grafo completo do pipeline Blueprint.

    Fluxo:
        extrair → classificar → filtrar → validar
            ↓ (OK) → calcular → adaptar → rag → orcamento → END
            ↓ (CANCELADO) → END

    Human-in-the-loop:
        O nó "validar" pode chamar interrupt() para alertas críticos.
        O grafo pausa e aguarda resposta humana antes de continuar.

    Retorna:
        CompiledGraph pronto para .invoke()
    """
    g = StateGraph(BlueprintState)

    # ── Nós ──────────────────────────────────────────────────────────────
    g.add_node("extrair", node_extrair)
    g.add_node("classificar", node_classificar)
    g.add_node("filtrar", node_filtrar)
    g.add_node("validar", node_validar)
    g.add_node("calcular", node_calcular)
    g.add_node("adaptar", node_adaptar)
    g.add_node("rag_sinapi", node_rag)
    g.add_node("orcamento", node_orcamento)

    # ── Arestas lineares ─────────────────────────────────────────────────
    g.set_entry_point("extrair")
    g.add_edge("extrair", "classificar")
    g.add_edge("classificar", "filtrar")
    g.add_edge("filtrar", "validar")

    # ── Aresta condicional: validação ────────────────────────────────────
    g.add_conditional_edges("validar", decidir_apos_validacao, {
        "calcular": "calcular",
        "fim_validacao": END,
    })

    g.add_edge("calcular", "adaptar")

    # ── Aresta condicional: adaptação ────────────────────────────────────
    g.add_conditional_edges("adaptar", decidir_apos_adaptacao, {
        "rag": "rag_sinapi",
        "fim": END,
    })

    g.add_edge("rag_sinapi", "orcamento")
    g.add_edge("orcamento", END)

    # Compila com checkpointer para suportar interrupt()
    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


# Singleton do grafo compilado
_grafo_compilado = None


def get_grafo_blueprint():
    """Retorna o grafo compilado (singleton)."""
    global _grafo_compilado
    if _grafo_compilado is None:
        _grafo_compilado = construir_grafo_blueprint()
    return _grafo_compilado
