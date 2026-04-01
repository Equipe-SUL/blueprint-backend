from __future__ import annotations

import json
import re
import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable
from time import perf_counter

from langchain_core.prompts import ChatPromptTemplate

from .client import get_chat_llm
from .schemas import ItensProjetoLLMSaida
from .prompts import INTERPRETATION_SYSTEM_PROMPT, INTERPRETATION_USER_PROMPT

# Uso principal do interpretation.py é receber a extração DXF, interpretar o JSON e devolver uma lista de itens de projeto (descricao, unidade, quantidade, preco_unitario) para serem inseridos no banco.
# Algoritmo:
# 1. Recebe JSON da extração do DXF.
# 2. Normaliza formação do texto
# 3. Divide textos em blocos (chunks) para caber no contexto da LLM
# 4. Em cada chunk: monta o prompt, chama a LLM pelo client.py e por fim prepara a resposta em JSON com o schemas.py 
# 5. Junta tudo em uma resposta final (merge)

CHUNK_SIZE = 200  # Número de entradas por chunk, ajuda a controlar o tamanho do contexto para a LLM. Da pra ajustar conforme necessidade e limites da LLM.
CHUNK_CONCURRENCY = 4  # Limita quantos chunks chamam a LLM ao mesmo tempo para reduzir o tempo total sem sobrecarregar.
_RE_MTEXT_FMT = re.compile(r"\{\\[^;]+;([^}]*)\}") # Limpa formatações do MTEXT do DXF, mantendo o texto dentro das chaves (ex: {\\H1.5x;Texto} vira "Texto")

# TODO: Limpeza de dados extraidos do DXF - remove formatação MTEXT, quebras e símbolos, precisamos disso pra LLM interpretar melhor.
def _clean_mtext(texto: str) -> str:
    txt = (texto or "").strip()
    if not txt:
        return ""
    txt = txt.replace("\\P", " ")
    txt = _RE_MTEXT_FMT.sub(r"\1", txt)
    txt = txt.replace("%%C", "Ø")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

# TODO: Dividir para conquistar! 
# Divide a lista extraida de textos de blocos menores (chunks) para processar com a LLM, garantindo que cada bloco tenha um tamanho adequado para o contexto da LLM.
def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]

# TODO: Merge inteligente das saídas da LLM - consolida os itens interpretados de cada chunk, somando quantidades de itens iguais e junta itens.
def _merge_saidas(saidas: list[ItensProjetoLLMSaida]) -> ItensProjetoLLMSaida:
    itens_por_chave: dict[tuple[str, str], dict[str, Any]] = {}
    avisos: list[str] = []

    for saida in saidas:
        avisos.extend(saida.avisos or [])
        for item in saida.itens:
            desc = " ".join(item.descricao.strip().split())
            un = item.unidade.strip()
            chave = (desc.lower(), un.lower())

            if chave not in itens_por_chave:
                itens_por_chave[chave] = {
                    "descricao": desc,
                    "unidade": un,
                    "quantidade": Decimal(item.quantidade),
                    "preco_unitario": Decimal(item.preco_unitario),
                    "origem": item.origem,
                    "justificativa": item.justificativa,
                }
            else:
                itens_por_chave[chave]["quantidade"] += Decimal(item.quantidade)
                # preço_unitario e origem ficam como vieram (por enquanto)

    merged = {
        "itens": list(itens_por_chave.values()),
        "avisos": avisos,
    }
    return ItensProjetoLLMSaida.model_validate(merged)

# TODO: oquestra tudo acima
# Chunking + chamadas LLM + merge para saída final 
def interpretar_itens_extraidos_dxf(
    itens_extraidos: dict[str, Any],
    *,
    tipo_projeto: list[str] | None = None,
) -> ItensProjetoLLMSaida:
    t_start = perf_counter()
    print("[interpretar] início do fluxo", flush=True)
    # 1) Normaliza os textos (só formatação)
    textos_legenda = itens_extraidos.get("textos_legenda") or []
    textos_norm: list[dict[str, Any]] = []
    for row in textos_legenda:
        textos_norm.append(
            {
                "texto": _clean_mtext(str(row.get("texto", ""))),
                "layer": str(row.get("layer", "")),
            }
        )
    
    # remove entradas vazias (isso é só sanidade)
    textos_norm = [r for r in textos_norm if r["texto"]]

    # 2) Contexto fixo (vai junto em todos os chunks)
    base_context = {
        "tipo_projeto": tipo_projeto or [],
        "ambientes": itens_extraidos.get("ambientes") or [],
        "quantidades_por_etiqueta": itens_extraidos.get("quantidades_por_etiqueta") or [],
    }

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", INTERPRETATION_SYSTEM_PROMPT),
            ("user", INTERPRETATION_USER_PROMPT),
        ]
    )

    llm = get_chat_llm().with_structured_output(ItensProjetoLLMSaida, method="json_schema")
    chain = prompt | llm

    saidas: list[ItensProjetoLLMSaida] = []
    base_json = json.dumps(base_context, ensure_ascii=False)

    # 3) MAP: interpreta chunks em paralelo limitado (async) pra reduzir o tempo total de LLM
    async def _processar_chunks() -> list[ItensProjetoLLMSaida]:
        sem = asyncio.Semaphore(CHUNK_CONCURRENCY)

        async def _invocar_chunk(idx: int, chunk: list[dict[str, Any]]):
            chunk_json = json.dumps(chunk, ensure_ascii=False)
            t_chunk_start = perf_counter()
            print(f"[interpretar] chunk {idx} -> {len(chunk)} entradas", flush=True)
            async with sem:  # garante limite de concorrência
                saida = await chain.ainvoke({"base_json": base_json, "chunk_json": chunk_json})
            print(
                f"[interpretar] chunk {idx} concluído em {perf_counter() - t_chunk_start:.2f}s",
                flush=True,
            )
            return saida

        tasks = [
            _invocar_chunk(idx, chunk)
            for idx, chunk in enumerate(_chunked(textos_norm, CHUNK_SIZE), start=1)
        ]
        return await asyncio.gather(*tasks)

    saidas.extend(asyncio.run(_processar_chunks()))

    # 4) REDUCE: consolida tudo em uma única saída
    t_merge_start = perf_counter()
    resultado_final = _merge_saidas(saidas)
    print(
        f"[interpretar] merge concluído em {perf_counter() - t_merge_start:.2f}s; "
        f"total {perf_counter() - t_start:.2f}s",
        flush=True,
    )
    return resultado_final