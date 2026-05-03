from typing import List, Dict
from apps.projetos.ai.rag.vectorstore import get_vector_store

def buscar_itens_para_selecao(descricao_cad: str, top_k: int = 5) -> List[Dict]:
    """Busca as opções na base vetorial e devolve uma lista de dicionários."""
    vector_store = get_vector_store()
    resultados = vector_store.similarity_search(descricao_cad, k=top_k)
    
    opcoes = []
    for doc in resultados:
        opcoes.append({
            "codigo": doc.metadata.get("codigo", "S/N"),
            "descricao": doc.page_content,
            "unidade": doc.metadata.get("unidade", "-"),
            "grupo": doc.metadata.get("grupo", "-"),
            "preco_unitario": float(doc.metadata.get("preco_unitario", 0)),
        })
    return opcoes

def gerar_sugestoes_orcamento(dados_cad_json: List[Dict]) -> List[Dict]:
    """Prepara a planilha de sugestões para a interface do usuário."""
    planilha_sugestoes = []

    for item in dados_cad_json:
        descricao_cad = item.get("description", "")
        # Traz o Top 5
        opcoes_sinapi = buscar_itens_para_selecao(descricao_cad, top_k=5)
        
        quantidade = item.get("quantity", item.get("volume_m3", 0))
        
        linha = {
            "id_cad": item.get("id"),
            "item_original": descricao_cad,
            "quantidade": quantidade,
            "opcoes_sinapi": opcoes_sinapi
        }
        
        planilha_sugestoes.append(linha)

    return planilha_sugestoes


def calcular_orcamento_final(
    sugestoes: List[Dict], 
    selecoes: Dict[str, int] = None,
    taxa_bdi: float = 0.0
) -> Dict:
    """
    Calcula o orçamento final com base nas sugestões SINAPI.

    Parâmetros:
        sugestoes  : saída do gerar_sugestoes_orcamento()
        selecoes   : dict mapeando id_cad -> índice da opção SINAPI escolhida (0-4)
                     Se None, usa automaticamente a primeira opção (índice 0)
        taxa_bdi   : percentual de BDI (ex: 25.50 para 25,50%)
    
    Retorna:
        dict com itens orçados, subtotal, BDI e total geral
    """
    itens_orcados = []
    subtotal = 0.0
    
    for item in sugestoes:
        id_cad = item.get("id_cad", "")
        quantidade = float(item.get("quantidade", 0))
        opcoes = item.get("opcoes_sinapi", [])
        
        if not opcoes:
            continue
        
        # Seleciona a opção SINAPI (pela escolha do usuário ou a primeira)
        idx = 0
        if selecoes and id_cad in selecoes:
            idx = selecoes[id_cad]
        
        opcao_escolhida = opcoes[min(idx, len(opcoes) - 1)]
        preco_unitario = float(opcao_escolhida.get("preco_unitario", 0))
        custo_total = round(quantidade * preco_unitario, 2)
        subtotal += custo_total
        
        itens_orcados.append({
            "id_cad": id_cad,
            "descricao_cad": item.get("item_original", ""),
            "sinapi_codigo": opcao_escolhida.get("codigo", ""),
            "sinapi_descricao": opcao_escolhida.get("descricao", ""),
            "sinapi_unidade": opcao_escolhida.get("unidade", ""),
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
            "custo_total": custo_total,
        })
    
    # Calcula BDI
    valor_bdi = round(subtotal * (taxa_bdi / 100), 2)
    total_geral = round(subtotal + valor_bdi, 2)
    
    return {
        "itens": itens_orcados,
        "resumo": {
            "total_itens": len(itens_orcados),
            "subtotal": subtotal,
            "taxa_bdi_percentual": taxa_bdi,
            "valor_bdi": valor_bdi,
            "total_geral": total_geral,
        }
    }