"""
grafo_novo — Grafo LangGraph para geração do Memorial Descritivo.

Pipeline de 4 nós:
  1. node_upload_cadastro    — Input & validação de metadados
  2. node_extraction_manual  — Extração determinística do DXF (ezdxf)
  3. node_llm_analyst        — Agente LLM auditor (Memorial Descritivo)
  4. node_storage_export     — Persistência no DB + exportação PDF

Uso:
    from apps.projetos.ai.grafo_novo.builder_descritivo import get_grafo_descritivo

    grafo = get_grafo_descritivo()
    resultado = grafo.invoke({
        "caminho_dxf": "planta.dxf",
        "projeto_id": 1,
        "metadados_obra": {"nome": "Residência X", ...},
    }, config={"configurable": {"thread_id": "..."}})
"""
