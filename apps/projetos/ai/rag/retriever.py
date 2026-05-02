# Em apps/projetos/ai/rag/retriever.py

def buscar_itens_para_selecao(descricao_cad: str, top_k: int = 5):
    vector_store = get_vector_store()
    resultados = vector_store.similarity_search(descricao_cad, k=top_k)
    
    opcoes = []
    for doc in resultados:
        opcoes.append({
            "codigo": doc.metadata.get("codigo"),
            "descricao": doc.page_content,
            "unidade": doc.metadata.get("unidade"),
            "grupo": doc.metadata.get("grupo")
        })
    return opcoes