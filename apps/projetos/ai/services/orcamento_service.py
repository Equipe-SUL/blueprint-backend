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
            "grupo": doc.metadata.get("grupo", "-")
        })
    return opcoes

def gerar_sugestoes_orcamento(dados_cad_json: List[Dict]) -> List[Dict]:
    """Prepara a planilha de sugestões para a interface do usuário."""
    planilha_sugestoes = []

    for item in dados_cad_json:
        descricao_cad = item.get("description", "")
        # Traz o Top 5
        opcoes_sinapi = buscar_itens_para_selecao(descricao_cad, top_k=5)
        
        linha = {
            "id_cad": item.get("id"),
            "item_original": descricao_cad,
            "quantidade": item.get("quantity", item.get("volume_m3", 0)),
            "opcoes_sinapi": opcoes_sinapi
        }
        
        planilha_sugestoes.append(linha)

    return planilha_sugestoes