from .embeddings import get_vector_store

def buscar_contexto_sinapi(termo_busca: str, k: int = 3) -> str:
    """
    Busca na base vetorial os 'k' itens da SINAPI mais parecidos com o termo de busca.
    Retorna uma string formatada pronta para ser injetada no Prompt da LLM.
    """
    if not termo_busca or not termo_busca.strip():
        return ""
        
    vector_store = get_vector_store()
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    
    # Executa a busca vetorial
    documentos_encontrados = retriever.invoke(termo_busca)
    
    if not documentos_encontrados:
        return "Nenhum material correspondente encontrado na SINAPI."
    
    # Formata os resultados em uma única string
    resultados_formatados = "\n".join([f"- {doc.page_content}" for doc in documentos_encontrados])
    
    return resultados_formatados