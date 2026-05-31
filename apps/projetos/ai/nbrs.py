"""
nbrs.py
=======
Integracao com NBRs (Normas Brasileiras) via RAG.

- Ingestion: apps/projetos/ai/rag/ingest_nbrs.py
- Busca: ChromaDB (nbrs_collection) com embeddings MiniLM
- Injecao no prompt: trechos relevantes das NBRs sao adicionados ao contexto do LLM
"""
import os, re
from typing import List, Optional

NBR_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "nbrs")


def gerar_contexto_nbrs(consulta: str, k: int = 4) -> str:
    """
    Busca chunks de NBRs relevantes no ChromaDB e retorna texto formatado.

    Args:
        consulta: Descricao do contexto da obra (ex: "residencial geminado banheiro cozinha agua")
        k: Numero de chunks a retornar

    Returns:
        String formatada com extratos das NBRs, ou "" se vazio/falha.
    """
    try:
        from apps.projetos.ai.rag.ingest_nbrs import gerar_contexto_nbrs as _rag_busca
        return _rag_busca(consulta, k=k)
    except Exception:
        return ""


def inject_nbrs_into_prompt(prompt: str, contexto_obra: Optional[str] = None, k: int = 4) -> str:
    """
    Injeta blocos de NBRs relevantes no final do prompt.

    Args:
        prompt: Prompt original (ex: SYSTEM_PROMPT_AUDITOR)
        contexto_obra: Descricao da obra para busca RAG (ex: "residencial geminado 48m2")
                       Se None, usa lista estatica baseada em nomes de arquivos
        k: Numero de chunks NBR a retornar via RAG

    Returns:
        Prompt com NBRs injetadas
    """
    if contexto_obra:
        # RAG: busca trechos reais das NBRs
        blocos = gerar_contexto_nbrs(contexto_obra, k=k)
        if not blocos:
            return prompt + "\n\n### ATENCAO: NBRs nao disponiveis via RAG\n"
        return prompt + "\n\n" + blocos
    else:
        # Fallback estatico: lista de NBRs por nome de arquivo
        blocos = _gerar_lista_estatica()
        if not blocos:
            return prompt
        return prompt + "\n" + blocos


def _gerar_lista_estatica() -> str:
    """Gera lista estatica de NBRs a partir dos nomes dos arquivos."""
    if not os.path.isdir(NBR_DIR):
        return ""

    linhas = ["\n### NORMAS TECNICAS (NBRs) DISPONIVEIS NO PROJETO\n"]
    for fname in sorted(os.listdir(NBR_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        nome = os.path.splitext(fname)[0]
        m = re.search(r'(\d{4,5})', fname)
        nbr = m.group(1) if m else "???"
        linhas.append(f"- NBR {nbr}: {nome}")

    linhas.append("""
INSTRUCAO FINAL - NORMAS TECNICAS:
- No JSON de saida, CRIE uma secao "normas_tecnicas" (array) listando as NBRs aplicaveis
- Para cada NBR citada, inclua: "nbr", "titulo" (extraido dos extratos acima), "aplicacao" (ambiente/sistema)
- Associe cada NBR aos ambientes identificados (ex: NBR 5626 para agua fria na cozinha/banho)
- Ex:
    "normas_tecnicas": [
        {"nbr": "NBR 5626", "titulo": "Sistemas Prediais de Agua Fria e Agua Quente", "aplicacao": "Banheiro e cozinha"},
        {"nbr": "NBR 9050", "titulo": "Acessibilidade", "aplicacao": "Banheiro acessivel"}
    ]
- Se nao houver NBRs relevantes para a obra, retorne array vazio: "normas_tecnicas": []
""")
    return "\n".join(linhas)
