from .embeddings import get_vector_store

import re


_DIAMETRO_RE = re.compile(r"%%[cC]\s*(\d+(?:[\.,]\d+)?)(?:\s*mm)?", re.IGNORECASE)
_MM_RE = re.compile(r"(\d+(?:[\.,]\d+)?)\s*mm\b", re.IGNORECASE)


def _normalizar_termo_busca(termo_busca: str) -> str:
    termo = (termo_busca or "").strip()
    if not termo:
        return termo

    # AutoCAD: '%%C40' representa símbolo de diâmetro + valor.
    termo = _DIAMETRO_RE.sub(r"diametro \1 mm", termo)
    termo = _MM_RE.sub(lambda m: f"{m.group(1)} mm", termo)
    termo = re.sub(r"\s+", " ", termo)
    return termo

def buscar_contexto_sinapi(termo_busca: str, k: int = 5, disciplina: str = None) -> str:
    """
    Realiza a busca semântica na base SINAPI filtrando pela disciplina 
    baseada nos TextChoices do Model Projeto.
    """
    if not termo_busca or not termo_busca.strip():
        return "Nenhum termo técnico extraído para busca."

    termo_busca_normalizado = _normalizar_termo_busca(termo_busca)

    # 1. Obtemos a conexão com o banco de vetores (ChromaDB)
    vector_store = get_vector_store()

    # 2. Estratégia de fallback de disciplina (muito importante):
    # Se a base foi importada como 'geral', o filtro por disciplina zera resultados.
    disciplina_slug = disciplina.lower().strip() if disciplina else None
    tentativas: list[tuple[dict | None, str]] = []
    if disciplina_slug:
        tentativas.append(({"disciplina": disciplina_slug}, f"disciplina='{disciplina_slug}'"))
        if disciplina_slug != "geral":
            tentativas.append(({"disciplina": "geral"}, "disciplina='geral'"))
        tentativas.append((None, "sem filtro"))
    else:
        tentativas.append((None, "sem filtro"))

    try:
        # 3. Executamos a busca por similaridade com fallback
        documentos_encontrados = []
        ultima_tentativa = ""
        for filtro, label in tentativas:
            ultima_tentativa = label
            search_kwargs = {"k": k}
            if filtro is not None:
                search_kwargs["filter"] = filtro
                print(f"[RAG] Tentativa com filtro {label}")
            else:
                print("[RAG] Tentativa sem filtro de disciplina")

            retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
            documentos_encontrados = retriever.invoke(termo_busca_normalizado)
            if documentos_encontrados:
                break

        if not documentos_encontrados:
            return (
                f"Atenção: Nenhum item correspondente encontrado na SINAPI para a "
                f"disciplina '{disciplina}'. Verifique se o termo '{termo_busca}' está correto. "
                f"(Última tentativa: {ultima_tentativa})"
            )

        # 4. Formatamos os resultados (inclui metadados quando existirem)
        contexto_formatado = "ITENS RELEVANTES DA TABELA SINAPI:\n"
        for i, doc in enumerate(documentos_encontrados, 1):
            meta = getattr(doc, "metadata", {}) or {}
            codigo = str(meta.get("codigo") or "").strip()
            tipo = str(meta.get("tipo") or "").strip()
            unidade = str(meta.get("unidade") or "").strip()
            preco = meta.get("preco")

            prefixo = f"{i}."
            if tipo:
                prefixo += f" TIPO={tipo};"
            if codigo:
                prefixo += f" CODIGO={codigo};"
            if unidade:
                prefixo += f" UNIDADE={unidade};"
            if preco is not None and preco != "":
                prefixo += f" PRECO={preco};"

            contexto_formatado += f"{prefixo} {doc.page_content}\n"

        return contexto_formatado

    except Exception as e:
        print(f" Erro na recuperação do RAG: {e}")
        return "Erro ao recuperar dados da base SINAPI."