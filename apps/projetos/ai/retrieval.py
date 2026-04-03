from .embeddings import get_vector_store
from apps.projetos.models import Projeto

def buscar_contexto_sinapi(termo_busca: str, k: int = 5, disciplina: str = None) -> str:
    """
    Realiza a busca semântica na base SINAPI filtrando pela disciplina 
    baseada nos TextChoices do Model Projeto.
    """
    if not termo_busca or not termo_busca.strip():
        return "Nenhum termo técnico extraído para busca."

    # 1. Obtemos a conexão com o banco de vetores (ChromaDB)
    vector_store = get_vector_store()

    # 2. Configuração do Filtro de Disciplina
    # Cruzamos o que vem da I.A. com as opções reais do seu models.py
    search_kwargs = {"k": k}
    
    if disciplina:
        # Normalizamos a disciplina para bater com as chaves do seu Model:
        # 'eletrica', 'hidraulica', 'alvenaria', 'spda', 'combate_a_incendio'
        disciplina_slug = disciplina.lower().strip()
        
        # O ChromaDB filtrará os documentos que possuem esse metadado 'disciplina'
        search_kwargs["filter"] = {"disciplina": disciplina_slug}
        print(f"[RAG] Filtrando busca SINAPI por disciplina: {disciplina_slug}")
    else:
        print("[RAG] Aviso: Busca realizada sem filtro de disciplina (busca geral).")

    # 3. Criamos o Retriever (o motor de busca)
    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

    try:
        # 4. Executamos a busca por similaridade
        documentos_encontrados = retriever.invoke(termo_busca)

        if not documentos_encontrados:
            return (
                f"Atenção: Nenhum item correspondente encontrado na SINAPI para a "
                f"disciplina '{disciplina}'. Verifique se o termo '{termo_busca}' está correto."
            )

        # 5. Formatamos os resultados para o prompt do Qwen
        contexto_formatado = "ITENS RELEVANTES DA TABELA SINAPI:\n"
        for i, doc in enumerate(documentos_encontrados, 1):
            # O page_content contém a descrição e o preço formatado no embeddings.py
            contexto_formatado += f"{i}. {doc.page_content}\n"

        return contexto_formatado

    except Exception as e:
        print(f" Erro na recuperação do RAG: {e}")
        return "Erro ao recuperar dados da base SINAPI."