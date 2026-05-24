"""
ingest_nbrs.py
==============
Extrai texto dos PDFs de NBRs, chunkifica e indexa no ChromaDB
para consulta via RAG durante a geracao do memorial descritivo.
"""
import os, re
import fitz  # PyMuPDF
from typing import List, Dict
from django.conf import settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from apps.projetos.ai.config import get_ai_config
from apps.projetos.ai.rag.embeddings import get_embedding_model

NBR_DIR = os.path.join(settings.BASE_DIR, "nbrs")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def extrair_texto_pdf(path: str) -> str:
    """Extrai todo o texto de um PDF usando PyMuPDF."""
    doc = fitz.open(path)
    texto = []
    for pagina in doc:
        texto.append(pagina.get_text())
    doc.close()
    return "\n".join(texto)


def chunkificar(texto: str, nbr_numero: str, nbr_titulo: str) -> List[Document]:
    """Divide o texto em chunks sobrepostos, preservando metadados da NBR."""
    paragrafos = re.split(r'\n\s*\n', texto)
    chunks = []
    buffer = ""
    for p in paragrafos:
        p = p.strip()
        if not p:
            continue
        if len(buffer) + len(p) < CHUNK_SIZE:
            buffer += "\n\n" + p if buffer else p
        else:
            if buffer:
                chunks.append(Document(
                    page_content=buffer,
                    metadata={"nbr": nbr_numero, "titulo": nbr_titulo, "origem": "nbr"},
                ))
            buffer = p

    if buffer:
        chunks.append(Document(
            page_content=buffer,
            metadata={"nbr": nbr_numero, "titulo": nbr_titulo, "origem": "nbr"},
        ))

    return chunks


def extrair_numero_nbr(fname: str) -> str:
    """Extrai o numero da NBR do nome do arquivo."""
    m = re.search(r'(\d{4,5})', fname)
    return m.group(1) if m else "0000"


def extrair_titulo_nbr(fname: str) -> str:
    """Extrai um titulo legivel do nome do arquivo."""
    nome = os.path.splitext(fname)[0]
    # Remove extensao e normaliza
    nome = nome.replace("_", " ").replace("-", " ").strip()
    return nome


def ingerir_nbrs():
    """Pipeline completo: le PDFs -> chunk -> embed -> ChromaDB."""
    if not os.path.isdir(NBR_DIR):
        print(f"ERRO: pasta {NBR_DIR} nao encontrada")
        return

    pdfs = sorted([f for f in os.listdir(NBR_DIR) if f.lower().endswith(".pdf")])
    print(f"NBRs encontradas: {len(pdfs)}\n")

    todos_chunks = []

    for fname in pdfs:
        path = os.path.join(NBR_DIR, fname)
        nbr_num = extrair_numero_nbr(fname)
        nbr_tit = extrair_titulo_nbr(fname)

        try:
            texto = extrair_texto_pdf(path)
            chars = len(texto)
            chunks = chunkificar(texto, nbr_num, nbr_tit)
            todos_chunks.extend(chunks)
            print(f"  NBR {nbr_num:>6s} | {nbr_tit[:50]:50s} | {chars:>6d} chars | {len(chunks):>3d} chunks")
        except Exception as e:
            print(f"  NBR {nbr_num:>6s} | ERRO: {e}")

    print(f"\nTotal chunks: {len(todos_chunks)}")

    # Indexar no ChromaDB
    config = get_ai_config()
    persist_dir = config.chroma_persist_path or os.path.join(settings.BASE_DIR, "chroma_db")
    os.makedirs(persist_dir, exist_ok=True)

    vectorstore = Chroma(
        collection_name="nbrs_collection",
        embedding_function=get_embedding_model(),
        persist_directory=persist_dir,
    )

    # Inserir em lotes
    batch_size = 100
    for i in range(0, len(todos_chunks), batch_size):
        batch = todos_chunks[i:i+batch_size]
        vectorstore.add_documents(batch)
        print(f"  Indexados: {min(i+batch_size, len(todos_chunks))}/{len(todos_chunks)}")

    print(f"\nIndexacao concluida! Total: {len(todos_chunks)} chunks em nbrs_collection")


def buscar_nbrs(consulta: str, k: int = 5) -> List[Document]:
    """Busca chunks de NBRs relevantes para a consulta."""
    config = get_ai_config()
    persist_dir = config.chroma_persist_path or os.path.join(settings.BASE_DIR, "chroma_db")

    vectorstore = Chroma(
        collection_name="nbrs_collection",
        embedding_function=get_embedding_model(),
        persist_directory=persist_dir,
    )

    resultados = vectorstore.similarity_search(consulta, k=k)
    return resultados


def gerar_contexto_nbrs(consulta: str, k: int = 4) -> str:
    """Busca NBRs relevantes e retorna como texto formatado para o prompt."""
    docs = buscar_nbrs(consulta, k=k)
    if not docs:
        return ""

    linhas = ["### EXTRATOS DE NORMAS TECNICAS (NBRs) RELEVANTES\n"]
    for i, doc in enumerate(docs, 1):
        nbr = doc.metadata.get("nbr", "?")
        titulo = doc.metadata.get("titulo", "")
        texto = doc.page_content.strip()[:500]
        linhas.append(f"[{i}] NBR {nbr} - {titulo}")
        linhas.append(f"    {texto}\n")

    return "\n".join(linhas)


# Management command hook
def run():
    ingerir_nbrs()


if __name__ == "__main__":
    import django; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings"); django.setup()
    ingerir_nbrs()
