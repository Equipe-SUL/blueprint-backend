"""
edges_descritivo.py
====================
Funções de roteamento condicional para o grafo do Memorial Descritivo.

Controla o fluxo:
  - Após extração: LLM analyst (com dados) ou END (sem dados / erro)
  - Após análise LLM: exportação (OK) ou END (erro)
"""

from apps.projetos.ai.grafo_novo.state_descritivo import DescritivoState


def decidir_apos_extracao(state: DescritivoState) -> str:
    """
    Decide o próximo nó após a extração manual.

    Se houve erro ou nenhuma entidade foi extraída, encerra o pipeline.
    Caso contrário, segue para o agente LLM.
    """
    if state.get("erro"):
        return "fim_erro"

    estatisticas = state.get("estatisticas", {})
    total = estatisticas.get("total_entidades", 0)
    total_ambientes = estatisticas.get("total_ambientes", 0)

    # Se não tem nenhuma entidade E nenhum ambiente, não há dados para análise
    if total == 0 and total_ambientes == 0:
        return "fim_erro"

    return "analise"


def decidir_apos_analise(state: DescritivoState) -> str:
    """
    Decide o próximo nó após a análise LLM.

    Se houve erro na LLM, encerra. Caso contrário, segue para exportação.
    """
    if state.get("erro"):
        return "fim_erro"

    # Verificar se o memorial descritivo foi gerado
    memorial = state.get("memorial_descritivo")
    if not memorial:
        return "fim_erro"

    return "exportar"
