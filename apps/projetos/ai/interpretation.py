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

# NOVO IMPORT: Trazendo o buscador do RAG que criamos no Passo 1
from .retrieval import buscar_contexto_sinapi

# Uso principal do interpretation.py é receber a extração DXF, interpretar o JSON e devolver uma lista de itens de projeto (descricao, unidade, quantidade, preco_unitario) para serem inseridos no banco.

CHUNK_SIZE = 200  
CHUNK_CONCURRENCY = 4  
_RE_MTEXT_FMT = re.compile(r"\{\\[^;]+;([^}]*)\}") 

def _clean_mtext(texto: str) -> str:
    txt = (texto or "").strip()
    if not txt:
        return ""
    txt = txt.replace("\\P", " ")
    txt = _RE_MTEXT_FMT.sub(r"\1", txt)
    txt = txt.replace("%%C", "Ø")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]

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

    merged = {
        "itens": list(itens_por_chave.values()),
        "avisos": avisos,
    }
    return ItensProjetoLLMSaida.model_validate(merged)


def interpretar_itens_extraidos_dxf(
    itens_extraidos: dict[str, Any],
    *,
    tipo_projeto: list[str] | None = None,
) -> ItensProjetoLLMSaida:
    t_start = perf_counter()
    print("[interpretar] início do fluxo", flush=True)
    
    # 1) Normaliza os textos
    textos_legenda = itens_extraidos.get("textos_legenda") or []
    textos_norm: list[dict[str, Any]] = []
    for row in textos_legenda:
        textos_norm.append(
            {
                "texto": _clean_mtext(str(row.get("texto", ""))),
                "layer": str(row.get("layer", "")),
            }
        )
    
    textos_norm = [r for r in textos_norm if r["texto"]]

    # 2) Contexto fixo
    base_context = {
        "tipo_projeto": tipo_projeto or [],
        "ambientes": itens_extraidos.get("ambientes") or [],
        "quantidades_por_etiqueta": itens_extraidos.get("quantidades_por_etiqueta") or [],
        # --- ADIÇÃO PARA O RAG DUPLO (A Visão da VLM) ---
        "relatorio_visual_vlm": itens_extraidos.get("analise_visual", "Não disponível") 
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

    async def _processar_chunks() -> list[ItensProjetoLLMSaida]:
        sem = asyncio.Semaphore(CHUNK_CONCURRENCY)

        async def _invocar_chunk(idx: int, chunk: list[dict[str, Any]]):
            chunk_json = json.dumps(chunk, ensure_ascii=False)
            t_chunk_start = perf_counter()
            print(f"[interpretar] chunk {idx} -> {len(chunk)} entradas", flush=True)
            
            # --- INÍCIO DA INTEGRAÇÃO RAG ---
            # Extraímos as palavras deste chunk para usar como busca na SINAPI
            textos_do_chunk = " ".join([item["texto"] for item in chunk])
            # Limitamos a busca aos primeiros 500 caracteres para ser rápido
            termo_para_busca = textos_do_chunk[:500] 
            
            # Buscamos no ChromaDB usando asyncio.to_thread para não travar o loop assíncrono
            contexto_sinapi = await asyncio.to_thread(buscar_contexto_sinapi, termo_para_busca, 5)
            # --- FIM DA INTEGRAÇÃO RAG ---

            async with sem:
                saida = await chain.ainvoke({
                    "base_json": base_json, 
                    "chunk_json": chunk_json,
                    "contexto_sinapi": contexto_sinapi # Injetamos a SINAPI no Prompt!
                })
                
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