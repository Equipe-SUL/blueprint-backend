"""
edges.py
========
Funções de roteamento condicional para o grafo LangGraph Blueprint.

Controla o fluxo:
  - Após validação: calcular (OK) ou END (cancelado pelo humano)
  - Após adaptação: RAG (com itens) ou END (sem itens)
"""

from apps.projetos.ai.graph.state import BlueprintState


def decidir_apos_validacao(state: BlueprintState) -> str:
    """
    Decide o próximo nó após a validação.

    Se a validação passou (validacao_ok=True), segue para o cálculo.
    Se não, o pipeline termina (o human-in-the-loop já tratou no nó).
    """
    if state.get("validacao_ok", True):
        return "calcular"
    return "fim_validacao"


def decidir_apos_adaptacao(state: BlueprintState) -> str:
    """Decide se deve seguir para o RAG ou parar (sem itens)."""
    itens = state.get("itens_adaptados", [])
    if not itens:
        return "fim"
    return "rag"
