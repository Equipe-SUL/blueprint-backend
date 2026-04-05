import asyncio
import json
from typing import Any, List, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .client import get_chat_llm
from .prompts import INTERPRETATION_SYSTEM_PROMPT, INTERPRETATION_USER_PROMPT
from .retrieval import buscar_contexto_sinapi
# CORREÇÃO 1: Ponto único para importar do mesmo diretório e classes atualizadas
from .schemas import AvisoLLM, ItemProjetoLLM, ItensProjetoLLMSaida

CHUNK_SIZE = 512
CHUNK_CONCURRENCY = 5
MAX_RAG_QUERY_CHARS = 6000

def interpretar_itens_extraidos_dxf(
    itens_extraidos: Dict[str, Any], 
    tipo_projeto: List[str]
) -> ItensProjetoLLMSaida: # CORREÇÃO 2: Tipagem de saída atualizada
    """
    Função principal que coordena a interpretação dos dados do DXF
    usando RAG (SINAPI) e contexto visual da VLM.
    """
    print(f"[interpretar] início do fluxo para {len(itens_extraidos.get('textos_legenda', []))} itens")
    
    textos = itens_extraidos.get("textos_legenda", [])
    chunks = [textos[i : i + CHUNK_SIZE] for i in range(0, len(textos), CHUNK_SIZE)]

    disciplina = tipo_projeto[0] if tipo_projeto else None
    partes_busca: List[str] = []
    tamanho_atual = 0
    for item in textos:
        t = (item.get("texto") or "").strip()
        if not t:
            continue
        # +1 por causa do espaço entre partes
        incremento = len(t) + (1 if partes_busca else 0)
        if tamanho_atual + incremento > MAX_RAG_QUERY_CHARS:
            restante = MAX_RAG_QUERY_CHARS - tamanho_atual
            if restante > 1:
                # garante ao menos 1 char de texto além do espaço
                if partes_busca:
                    restante -= 1
                partes_busca.append(t[:restante])
            break
        partes_busca.append(t)
        tamanho_atual += incremento

    termo_busca_global = " ".join(partes_busca).strip()

    try:
        contexto_sinapi_global = buscar_contexto_sinapi(
            termo_busca_global or "texto tecnico de projeto",
            k=10,
            disciplina=disciplina,
        )
    except Exception as e:
        contexto_sinapi_global = (
            "Atenção: Falha ao consultar a base SINAPI (RAG). "
            f"Detalhes: {type(e).__name__}: {str(e)[:300]}"
        )
    
    base_context = {
        "tipo_projeto": tipo_projeto or [],
        "ambientes": itens_extraidos.get("ambientes") or [],
        "quantidades_por_etiqueta": itens_extraidos.get("quantidades_por_etiqueta") or {},
        "relatorio_visual_vlm": itens_extraidos.get("analise_visual", "Não disponível")
    }

    # CORREÇÃO 3: Usando o PydanticOutputParser com o schema correto
    parser = PydanticOutputParser(pydantic_object=ItensProjetoLLMSaida)
    llm = get_chat_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", INTERPRETATION_SYSTEM_PROMPT),
        ("user", INTERPRETATION_USER_PROMPT),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser

    def _dedup_avisos(avisos: List[AvisoLLM]) -> List[AvisoLLM]:
        vistos: set[tuple[str, str, str, str | None]] = set()
        saida: List[AvisoLLM] = []
        for a in avisos:
            key = (a.nivel, a.categoria, a.mensagem, a.referencia)
            if key in vistos:
                continue
            vistos.add(key)
            saida.append(a)
        return saida

    def _filtrar_itens_somente_sinapi(itens: List[ItemProjetoLLM], avisos: List[AvisoLLM]) -> List[ItemProjetoLLM]:
        itens_validos: List[ItemProjetoLLM] = []
        for item in itens:
            if getattr(item, "origem", None) != "sinapi":
                avisos.append(
                    AvisoLLM(
                        nivel="ALTO",
                        categoria="ITEM_REJEITADO",
                        mensagem="Item descartado por estar fora da SINAPI (origem != 'sinapi').",
                        referencia=(item.descricao or None),
                    )
                )
                continue
            if not (item.codigo_sinapi and str(item.codigo_sinapi).strip()):
                avisos.append(
                    AvisoLLM(
                        nivel="CRITICO",
                        categoria="ITEM_REJEITADO",
                        mensagem="Item descartado por não conter codigo_sinapi (match SINAPI obrigatório nesta fase).",
                        referencia=(item.descricao or None),
                    )
                )
                continue
            itens_validos.append(item)
        return itens_validos

    async def _invocar_chunk(chunk: List[Dict[str, Any]], index: int) -> ItensProjetoLLMSaida:
        print(f"[interpretar] processando chunk {index+1}...")

        contexto_sinapi = contexto_sinapi_global

        try:
            saida = await chain.ainvoke({
                "base_json": json.dumps(base_context, ensure_ascii=False),
                "contexto_sinapi": contexto_sinapi,
                "chunk_json": json.dumps(chunk, ensure_ascii=False),
            })
            # Pós-processamento: reforça contrato (sem itens fora da SINAPI)
            avisos_chunk: List[AvisoLLM] = list(saida.avisos or [])
            itens_filtrados = _filtrar_itens_somente_sinapi(list(saida.itens or []), avisos_chunk)
            return ItensProjetoLLMSaida(itens=itens_filtrados, avisos=_dedup_avisos(avisos_chunk))
        except Exception as e:
            print(f"❌ Erro no chunk {index+1}: {e}")
            erro_resumido = f"{type(e).__name__}: {str(e)}"
            if len(erro_resumido) > 900:
                erro_resumido = erro_resumido[:900] + "..."
            # Em caso de erro, devolvemos o objeto vazio, mas com o aviso
            return ItensProjetoLLMSaida(
                itens=[],
                avisos=[
                    AvisoLLM(
                        nivel="CRITICO",
                        categoria="FALHA_TECNICA_CHUNK",
                        mensagem=f"Falha técnica no chunk {index+1}: {erro_resumido}",
                    )
                ],
            )

    async def _processar_chunks():
        semaphore = asyncio.Semaphore(CHUNK_CONCURRENCY)
        async def sem_task(chunk, i):
            async with semaphore:
                return await _invocar_chunk(chunk, i)
        
        tasks = [sem_task(c, i) for i, c in enumerate(chunks)]
        return await asyncio.gather(*tasks)

    resultados_chunks = asyncio.run(_processar_chunks())

    # Consolidação dos resultados
    todos_itens = []
    todos_avisos: List[AvisoLLM] = []

    for res in resultados_chunks:
        todos_itens.extend(res.itens)
        if res.avisos:
            todos_avisos.extend(res.avisos)

    # Dedup final de avisos + reforço final do contrato
    avisos_finais = _dedup_avisos(todos_avisos)
    itens_finais = _filtrar_itens_somente_sinapi(list(todos_itens), avisos_finais)

    return ItensProjetoLLMSaida(itens=itens_finais, avisos=_dedup_avisos(avisos_finais))