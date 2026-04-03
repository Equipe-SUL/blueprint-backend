import asyncio
import json
from typing import Any, List, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .client import get_chat_llm
from .prompts import INTERPRETATION_SYSTEM_PROMPT, INTERPRETATION_USER_PROMPT
from .retrieval import buscar_contexto_sinapi
# CORREÇÃO 1: Ponto único para importar do mesmo diretório e classes atualizadas
from .schemas import ItemProjetoLLM, ItensProjetoLLMSaida

CHUNK_SIZE = 5
CHUNK_CONCURRENCY = 1

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

    async def _invocar_chunk(chunk: List[Dict[str, Any]], index: int) -> ItensProjetoLLMSaida:
        print(f"[interpretar] processando chunk {index+1}...")
        
        termo_busca = " ".join([i.get("texto", "") for i in chunk])
        disciplina = tipo_projeto[0] if tipo_projeto else None
        
        contexto_sinapi = await asyncio.to_thread(
            buscar_contexto_sinapi, 
            termo_busca, 
            k=5, 
            disciplina=disciplina
        )

        try:
            saida = await chain.ainvoke({
                "base_json": json.dumps(base_context, ensure_ascii=False),
                "contexto_sinapi": contexto_sinapi,
                "chunk_json": json.dumps(chunk, ensure_ascii=False),
            })
            return saida
        except Exception as e:
            print(f"❌ Erro no chunk {index+1}: {e}")
            # Em caso de erro, devolvemos o objeto vazio, mas com o aviso
            return ItensProjetoLLMSaida(itens=[], avisos=[f"Falha técnica no chunk {index+1}: {str(e)}"])

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
    todos_avisos = []

    for res in resultados_chunks:
        todos_itens.extend(res.itens)
        if res.avisos:
            todos_avisos.extend(res.avisos)

    return ItensProjetoLLMSaida(
        itens=todos_itens,
        avisos=list(set(todos_avisos))
    )