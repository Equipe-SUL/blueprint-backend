"""
orcamento_service.py
=====================
Servico de orcamento usando keyword filter + LLM (gemma4) para matching SINAPI.

Substitui a busca por embeddings (MiniLM) que era imprecisa para terminologia
de construcao civil.
"""
from typing import List, Dict, Optional
from apps.projetos.ai.sinapi_matcher import (
    buscar_por_palavras_chave,
    match_com_llm,
)


def buscar_itens_para_selecao(
    descricao_cad: str,
    top_k: int = 5,
    usar_llm: bool = True,
) -> List[Dict]:
    """
    Busca opcoes SINAPI por keyword filter + LLM.

    1. Verifica estimativas CUB (para servicos sem codigo SINAPI direto)
    2. Filtra a tabela Referencia por palavras-chave extraidas da descricao
    3. Opcionalmente usa LLM (gemma4) para escolher o melhor candidato
    4. Retorna lista de dicionarios com ESTIMATIVA em primeira posicao se for o caso

    Args:
        descricao_cad: Descricao do item extraido do CAD
        top_k: Numero maximo de candidatos a retornar (excluindo ESTIMATIVA)
        usar_llm: Se True, tenta matching com LLM e marca a melhor opcao

    Returns:
        Lista de dicts com codigo, descricao, unidade, grupo, preco_unitario
    """
    # 0. LLM matching (pode retornar ESTIMATIVA antes de buscar SINAPI)
    cod_escolhido = None
    confianca_llm = "baixa"
    resultado_llm = None
    if usar_llm:
        resultado = match_com_llm(descricao_cad)
        resultado_llm = resultado
        cod_escolhido = resultado.get("codigo_escolhido")
        confianca_llm = resultado.get("confianca", "baixa")

    # 1. Verificar se LLM retornou estimativa CUB
    is_estimativa = (
        resultado_llm is not None
        and resultado_llm.get("_tipo_estimativa") == "CUB"
        and confianca_llm != "baixa"
    )

    # 2. Keyword filter (busca ampla para incluir Kits, depois filtra)
    candidatos = buscar_por_palavras_chave(descricao_cad, top_k=30)

    # 3. Montar resposta
    opcoes = []

    # ESTIMATIVA CUB sempre na primeira posicao (se houver)
    if is_estimativa:
        preco = resultado_llm.get("_preco_estimado", 0)
        unidade = resultado_llm.get("_unidade_estimada", "un")
        desc_est = resultado_llm.get("descricao_escolhida", "")
        opcoes.append({
            "codigo": cod_escolhido,
            "descricao": f"ESTIMATIVA CUB | {desc_est} | {resultado_llm.get('justificativa', '')}",
            "unidade": unidade,
            "grupo": "ESTIMATIVA",
            "preco_unitario": preco,
            "_selecionado": True,
        })

    if candidatos:
        for c in candidatos[:top_k]:
            selecionado = (
                not is_estimativa
                and cod_escolhido is not None
                and c["codigo"] == cod_escolhido
                and confianca_llm != "baixa"
            )
            opcoes.append({
                "codigo": c["codigo"],
                "descricao": f"Grupo: {c['grupo']} | Código: {c['codigo']} | "
                             f"Descrição: {c['descricao']} (Unidade: {c['unidade']})",
                "unidade": c["unidade"],
                "grupo": c["grupo"],
                "preco_unitario": c["preco_unitario"],
                "_selecionado": selecionado,
            })

        # Se LLM escolheu codigo SINAPI que nao esta no top_k, adiciona
        if cod_escolhido and confianca_llm != "baixa" and not is_estimativa and not any(o["codigo"] == cod_escolhido for o in opcoes):
            for c in candidatos:
                if c["codigo"] == cod_escolhido:
                    opcoes.insert(1 if is_estimativa else 0, {
                        "codigo": c["codigo"],
                        "descricao": f"Grupo: {c['grupo']} | Código: {c['codigo']} | "
                                     f"Descrição: {c['descricao']} (Unidade: {c['unidade']})",
                        "unidade": c["unidade"],
                        "grupo": c["grupo"],
                        "preco_unitario": c["preco_unitario"],
                        "_selecionado": True,
                    })
                    break

    # NUNCA forca selecao se LLM disse que nao ha matching adequado
    # (deixar _selecionado = False para todos significa "sem matching SINAPI")

    return opcoes


def gerar_sugestoes_orcamento(
    dados_cad_json: List[Dict],
    usar_llm: bool = True,
) -> List[Dict]:
    """Prepara a planilha de sugestoes para a interface do usuario."""
    planilha_sugestoes = []

    for item in dados_cad_json:
        descricao_cad = item.get("description", "")
        opcoes_sinapi = buscar_itens_para_selecao(descricao_cad, top_k=5, usar_llm=usar_llm)

        quantidade = item.get("quantity", item.get("volume_m3", 0))

        # Encontrar o indice selecionado (se houver)
        idx_selecionado = next(
            (i for i, o in enumerate(opcoes_sinapi) if o.get("_selecionado")),
            None
        )

        linha = {
            "id_cad": item.get("id"),
            "item_original": descricao_cad,
            "quantidade": quantidade,
            "unidade": item.get("unidade", "un"),
            "opcoes_sinapi": opcoes_sinapi,
            "selecao_automatica": idx_selecionado,
            "tipo": item.get("type", "desconhecido"),
        }

        planilha_sugestoes.append(linha)

    return planilha_sugestoes


def calcular_orcamento_final(
    sugestoes: List[Dict],
    selecoes: Optional[Dict[str, int]] = None,
    taxa_bdi: float = 0.0,
) -> Dict:
    """
    Calcula o orcamento final.

    Args:
        sugestoes: Saida do gerar_sugestoes_orcamento()
        selecoes: dict mapeando id_cad -> indice da opcao SINAPI escolhida
                  Se None, usa a selecao automatica do LLM (campo _selecionado)
        taxa_bdi: Percentual de BDI (ex: 25.50 para 25,50%)

    Returns:
        dict com itens orcados, subtotal, BDI e total geral
    """
    itens_orcados = []
    subtotal = 0.0

    for item in sugestoes:
        id_cad = item.get("id_cad", "")
        quantidade = float(item.get("quantidade", 0))
        opcoes = item.get("opcoes_sinapi", [])

        if not opcoes or quantidade == 0:
            continue

        # Determinar qual opcao usar
        if selecoes and id_cad in selecoes:
            # Selecao manual do usuario
            idx = selecoes[id_cad]
        else:
            # Usar selecao automatica (LLM)
            auto = item.get("selecao_automatica")
            if auto is None:
                # Sem matching SINAPI - pula este item
                continue
            idx = auto

        idx = min(idx, len(opcoes) - 1)
        opcao = opcoes[idx]
        preco_unitario = float(opcao.get("preco_unitario", 0))
        custo_total = round(quantidade * preco_unitario, 2)
        subtotal += custo_total

        itens_orcados.append({
            "id_cad": id_cad,
            "descricao_cad": item.get("item_original", ""),
            "sinapi_codigo": opcao.get("codigo", ""),
            "sinapi_descricao": opcao.get("descricao", ""),
            "sinapi_unidade": opcao.get("unidade", ""),
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
            "custo_total": custo_total,
            "selecionado_por_llm": opcao.get("_selecionado", False),
        })

    valor_bdi = round(subtotal * (taxa_bdi / 100), 2)
    total_geral = round(subtotal + valor_bdi, 2)

    return {
        "itens": itens_orcados,
        "resumo": {
            "total_itens": len(itens_orcados),
            "total_com_itens": sum(1 for i in sugestoes if i.get("selecao_automatica") is not None),
            "total_sem_itens": sum(1 for i in sugestoes if i.get("selecao_automatica") is None),
            "subtotal": subtotal,
            "taxa_bdi_percentual": taxa_bdi,
            "valor_bdi": valor_bdi,
            "total_geral": total_geral,
        }
    }
