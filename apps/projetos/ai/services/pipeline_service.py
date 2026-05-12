"""
pipeline_service.py
====================
Orquestrador do fluxo completo via LangGraph:
    DXF → Extração → Classificação → Filtragem → Validação
    → Cálculo → Adaptação → RAG SINAPI → Orçamento Final

Delega TODA a orquestração para o grafo LangGraph,
mantendo apenas a interface pública.

Suporta human-in-the-loop:
  - Quando o grafo interrompe (interrupt), retorna os alertas
  - O chamador pode retomar com `retomar_pipeline()`
"""

import sys
import uuid

# Força o encoding UTF-8 no terminal do Windows para evitar erros com emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


from langgraph.types import Command


def processar_dxf_completo(caminho_dxf: str, projeto_id: int = None) -> dict:
    """
    Pipeline completo via LangGraph: DXF → Memorial → RAG → Orçamento.

    Parâmetros:
        caminho_dxf : caminho absoluto do arquivo .dxf
        projeto_id  : ID do projeto no banco (para BDI e organização)

    Retorna:
        dict com:
          - sucesso: bool
          - memorial_calculo: JSON da etapa de cálculo
          - itens_adaptados: JSON intermediário
          - sugestoes_rag: sugestões SINAPI
          - orcamento_final: orçamento com BDI
          - alertas: alertas de validação (se houver)
          - etapa_atual: última etapa completada
          - erro: mensagem de erro (se houver)
          - thread_id: ID da thread (para retomar em caso de interrupt)
          - interrupt_info: dados do interrupt (se houver)
    """
    print("\n" + "=" * 70)
    print("[PIPELINE] Iniciando pipeline LangGraph Blueprint")
    print("=" * 70)

    try:
        from apps.projetos.ai.graph.builder import get_grafo_blueprint

        grafo = get_grafo_blueprint()

        # Gera um thread_id único para esta execução
        thread_id = str(uuid.uuid4())

        # Estado inicial
        estado_inicial = {
            "caminho_dxf": caminho_dxf,
            "projeto_id": projeto_id,
        }

        # Config com thread_id (obrigatório para checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        # Executa o grafo
        resultado = grafo.invoke(estado_inicial, config=config)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "sucesso": False,
            "erro": f"Erro no pipeline LangGraph: {str(e)}",
        }

    # ── Verifica se houve interrupt (human-in-the-loop) ──────────────────
    estado_grafo = grafo.get_state(config)

    if estado_grafo.next:
        # O grafo pausou — há um interrupt pendente
        print("\n[PIPELINE] ⏸️  Pipeline pausado — aguardando decisão humana.")

        # Extrai info do interrupt
        interrupt_info = None
        if hasattr(estado_grafo, "tasks"):
            for task in estado_grafo.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_info = task.interrupts[0].value
                    break

        return {
            "sucesso": False,
            "pausado": True,
            "thread_id": thread_id,
            "interrupt_info": interrupt_info,
            "alertas": resultado.get("alertas", []),
            "memorial_calculo": resultado.get("memorial_calculo"),
            "etapa_atual": resultado.get("etapa_atual", "validacao_pendente"),
            "erro": "Pipeline pausado: alertas críticos na validação. Aguardando decisão.",
        }

    # ── Monta a resposta ─────────────────────────────────────────────────
    etapa_atual = resultado.get("etapa_atual", "desconhecido")
    alertas = resultado.get("alertas", [])
    tem_orcamento = resultado.get("orcamento_final") is not None

    # Verifica se o pipeline parou por alertas críticos
    if etapa_atual == "validacao_completa" and not resultado.get("validacao_ok"):
        print("\n[PIPELINE] ⚠️  Pipeline interrompido na validação.")
        return {
            "sucesso": False,
            "erro": "Pipeline interrompido: alertas críticos na validação.",
            "alertas": alertas,
            "memorial_calculo": resultado.get("memorial_calculo"),
            "etapa_atual": etapa_atual,
        }

    if not tem_orcamento:
        # Pipeline terminou antes do orçamento (sem itens ou validação falhou)
        return {
            "sucesso": False,
            "erro": resultado.get("erro", "Nenhum item estrutural encontrado."),
            "alertas": alertas,
            "memorial_calculo": resultado.get("memorial_calculo"),
            "etapa_atual": etapa_atual,
        }

    orcamento = resultado["orcamento_final"]
    resumo = orcamento.get("resumo", {})

    print("\n" + "=" * 70)
    print(
        f"[PIPELINE] ✅ Concluído | "
        f"{resumo.get('total_itens', 0)} itens | "
        f"TOTAL: R$ {resumo.get('total_geral', 0):.2f}"
    )
    print("=" * 70)

    return {
        "sucesso": True,
        "memorial_calculo": resultado.get("memorial_calculo"),
        "itens_adaptados": resultado.get("itens_adaptados"),
        "sugestoes_rag": resultado.get("sugestoes_sinapi"),
        "orcamento_final": orcamento,
        "alertas": alertas,
        "etapa_atual": etapa_atual,
    }


def retomar_pipeline(thread_id: str, decisao: str = "continuar") -> dict:
    """
    Retoma um pipeline que foi pausado por interrupt (human-in-the-loop).

    Parâmetros:
        thread_id : ID da thread retornado em 'thread_id' quando pausado
        decisao   : 'continuar' para prosseguir ou 'cancelar' para parar

    Retorna:
        dict no mesmo formato de processar_dxf_completo()
    """
    print("\n" + "=" * 70)
    print(f"[PIPELINE] Retomando pipeline (thread={thread_id[:8]}..., decisão={decisao})")
    print("=" * 70)

    try:
        from apps.projetos.ai.graph.builder import get_grafo_blueprint

        grafo = get_grafo_blueprint()
        config = {"configurable": {"thread_id": thread_id}}

        # Retoma o grafo com a resposta do humano
        resultado = grafo.invoke(
            Command(resume=decisao),
            config=config,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "sucesso": False,
            "erro": f"Erro ao retomar pipeline: {str(e)}",
        }

    # ── Monta a resposta ─────────────────────────────────────────────────
    etapa_atual = resultado.get("etapa_atual", "desconhecido")
    alertas = resultado.get("alertas", [])
    tem_orcamento = resultado.get("orcamento_final") is not None

    if etapa_atual == "validacao_completa" and not resultado.get("validacao_ok"):
        return {
            "sucesso": False,
            "erro": "Pipeline cancelado pelo usuário na validação.",
            "alertas": alertas,
            "etapa_atual": etapa_atual,
        }

    if not tem_orcamento:
        return {
            "sucesso": False,
            "erro": resultado.get("erro", "Nenhum item estrutural encontrado."),
            "alertas": alertas,
            "memorial_calculo": resultado.get("memorial_calculo"),
            "etapa_atual": etapa_atual,
        }

    orcamento = resultado["orcamento_final"]
    resumo = orcamento.get("resumo", {})

    print("\n" + "=" * 70)
    print(
        f"[PIPELINE] ✅ Retomado e concluído | "
        f"{resumo.get('total_itens', 0)} itens | "
        f"TOTAL: R$ {resumo.get('total_geral', 0):.2f}"
    )
    print("=" * 70)

    return {
        "sucesso": True,
        "memorial_calculo": resultado.get("memorial_calculo"),
        "itens_adaptados": resultado.get("itens_adaptados"),
        "sugestoes_rag": resultado.get("sugestoes_sinapi"),
        "orcamento_final": orcamento,
        "alertas": alertas,
        "etapa_atual": etapa_atual,
    }
