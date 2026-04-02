from .embeddings import get_vector_store

def buscar_contexto_sinapi(termo_busca: str, k: int = 5, disciplina: str = None) -> str:
    """
    Realiza a busca vetorial no ChromaDB filtrando pela disciplina da engenharia.
    """
    if not termo_busca or not termo_busca.strip():
        return "Nenhum termo de busca fornecido."
        
    vector_store = get_vector_store()
    
    # Criamos o filtro se a disciplina for informada
    search_kwargs = {"k": k}
    if disciplina:
        # O ChromaDB busca nos metadados que configuramos no embeddings.py
        search_kwargs["filter"] = {"disciplina": disciplina.lower().strip()}
    
    # Criamos o buscador com o filtro aplicado
    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
    
    # Faz a busca
    docs = retriever.invoke(termo_busca)
    
    if not docs:
        return "Nenhum material correspondente encontrado na base SINAPI para esta disciplina."
    
    # Formata a resposta para a LLM ler
    contexto = "\n".join([f"- {d.page_content}" for d in docs])
    return contexto