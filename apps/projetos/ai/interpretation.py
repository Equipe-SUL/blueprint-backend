import asyncio
import json
from typing import Any, List, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .client import get_chat_llm
from .prompts import INTERPRETATION_SYSTEM_PROMPT, INTERPRETATION_USER_PROMPT
from .retrieval import buscar_contexto_sinapi  # Importamos o buscador do RAG
from ..schemas import ItemOrcamento, RespostaIA

# Configurações de processamento
CHUNK_SIZE = 5         # Quantos itens do DXF processamos por vez
CHUNK_CONCURRENCY = 1  # Mantemos em 1 para não travar PCs com pouca RAM

def interpretar_itens_extraidos_dxf(
    itens_extraidos: Dict[str, Any], 
    tipo_projeto: List[str]
) -> RespostaIA:
    """
    Função principal que coordena a interpretação dos dados do DXF
    usando RAG (SINAPI) e contexto visual da VLM.
    """
    print(f"[interpretar] início do fluxo para {len(itens_extraidos.get('textos_legenda', []))} itens")
    
    # 1) Preparação dos pedaços (chunks) para a IA não se perder
    textos = itens_extraidos.get("textos_legenda", [])
    chunks = [textos[i : i + CHUNK_SIZE] for i in range(0, len(textos), CHUNK_SIZE)]
    
    # 2) Contexto base que vai para todos os pedaços
    # Inclui o relatório visual que o Orquestrador injetou
    base_context = {
        "tipo_projeto": tipo_projeto or [],
        "ambientes": itens_extraidos.get("ambientes") or [],
        "quantidades_por_etiqueta": itens_extraidos.get("quantidades_por_etiqueta") or {},
        "relatorio_visual_vlm": itens_extraidos.get("analise_visual", "Não disponível")
    }

    parser = PydanticOutputParser(pydantic_object=RespostaIA)
    llm = get_chat_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", INTERPRETATION_SYSTEM_PROMPT),
        ("user", INTERPRETATION_USER_PROMPT),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser

    async def _invocar_chunk(chunk: List[Dict[str, Any]], index: int) -> RespostaIA:
        print(f"[interpretar] processando chunk {index+1}...")
        
        # --- BUSCA NO RAG (SINAPI) ---
        # Criamos um termo de busca baseado nos itens deste pedaço
        termo_busca = " ".join([i.get("texto", "") for i in chunk])
        
        # Filtramos pela primeira disciplina do projeto para ser preciso
        disciplina = tipo_projeto[0] if tipo_projeto else None
        
        # O asyncio.to_thread evita que a busca no banco trave o fluxo async
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
            return RespostaIA(itens=[], resumo=f"Erro no processamento: {str(e)}", avisos=["Falha técnica no chunk"])

    async def _processar_chunks():
        semaphore = asyncio.Semaphore(CHUNK_CONCURRENCY)
        async def sem_task(chunk, i):
            async with semaphore:
                return await _invocar_chunk(chunk, i)
        
        tasks = [sem_task(c, i) for i, c in enumerate(chunks)]
        return await asyncio.gather(*tasks)

    # Executa as tarefas assíncronas
    resultados_chunks = asyncio.run(_processar_chunks())

    # 3) Consolidação dos resultados
    todos_itens = []
    todos_avisos = []
    resumo_final = ""

    for res in resultados_chunks:
        todos_itens.extend(res.itens)
        if res.avisos:
            todos_avisos.extend(res.avisos)
        resumo_final += f" {res.resumo}"

    return RespostaIA(
        itens=todos_itens,
        resumo=resumo_final.strip(),
        avisos=list(set(todos_avisos)) # Remove avisos duplicados
    )