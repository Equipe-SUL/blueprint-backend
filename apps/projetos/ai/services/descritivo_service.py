"""
descritivo_service.py
======================
Orquestrador do fluxo Memorial Descritivo.

Função pública que conecta a view Django ao grafo LangGraph,
gerenciando thread_id e invocação.
"""

import uuid
import sys

# Força o encoding UTF-8 no terminal do Windows para evitar erros com emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def processar_memorial_descritivo(
    caminho_dxf: str,
    projeto_id: int = None,
    metadados_obra: dict = None,
) -> dict:
    """
    Executa o pipeline completo do Memorial Descritivo via LangGraph.

    Parâmetros:
        caminho_dxf   : Caminho absoluto do arquivo .DXF
        projeto_id    : ID do projeto no banco (FK para Projeto)
        metadados_obra: Dict com {nome, localizacao, tipo_construcao, padrao_acabamento}

    Retorna:
        dict com:
          - sucesso: bool
          - memorial_descritivo: JSON do memorial gerado
          - memorial_db_id: PK do registro salvo no banco
          - pdf_path: caminho do PDF gerado
          - inconsistencias: lista de alertas da auditoria
          - confianca: nível de confiança da análise
          - erro: mensagem de erro (se houver)
    """
    from apps.projetos.ai.grafo_novo.builder_descritivo import get_grafo_descritivo

    print("\n" + "=" * 70)
    print("[MEMORIAL DESCRITIVO] Iniciando pipeline...")
    print("=" * 70)

    # ── Montar estado inicial ────────────────────────────────────────────
    estado_inicial = {
        "caminho_dxf": caminho_dxf,
        "projeto_id": projeto_id,
        "metadados_obra": metadados_obra or {},
    }

    # ── Invocar grafo ────────────────────────────────────────────────────
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        grafo = get_grafo_descritivo()
        resultado = grafo.invoke(estado_inicial, config=config)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "sucesso": False,
            "erro": f"Falha na execução do grafo: {e}",
        }

    # ── Processar resultado ──────────────────────────────────────────────
    erro = resultado.get("erro")
    exportacao_ok = resultado.get("exportacao_ok", False)
    sucesso = exportacao_ok and not erro

    resposta = {
        "sucesso": sucesso,
        "memorial_descritivo": resultado.get("memorial_descritivo"),
        "memorial_db_id": resultado.get("memorial_db_id"),
        "pdf_path": resultado.get("pdf_path"),
        "inconsistencias": resultado.get("inconsistencias", []),
        "confianca": resultado.get("confianca_analise", "N/A"),
        "thread_id": thread_id,
        "etapa_final": resultado.get("etapa_atual", "desconhecida"),
    }

    if erro:
        resposta["erro"] = erro

    # ── Log final ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    if sucesso:
        print(f"[MEMORIAL DESCRITIVO] ✅ Pipeline concluído com sucesso!")
        print(f"   Memorial DB ID: {resposta['memorial_db_id']}")
        print(f"   PDF: {resposta['pdf_path']}")
        print(f"   Confiança: {resposta['confianca']}")
        print(f"   Inconsistências: {len(resposta['inconsistencias'])}")
    else:
        print(f"[MEMORIAL DESCRITIVO] ❌ Pipeline falhou: {erro}")
    print("=" * 70 + "\n")

    return resposta
