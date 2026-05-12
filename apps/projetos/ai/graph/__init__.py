"""
graph — Módulo LangGraph para orquestração do pipeline Blueprint.

Responsabilidades:
  - Definir o estado compartilhado (BlueprintState)
  - Implementar os nós do grafo (extração, classificação, filtragem, etc.)
  - Definir arestas condicionais (roteamento de fluxo)
  - Montar e compilar o grafo (com MemorySaver para human-in-the-loop)

Uso:
    from apps.projetos.ai.graph.builder import get_grafo_blueprint

    grafo = get_grafo_blueprint()
    resultado = grafo.invoke({"caminho_dxf": "arquivo.dxf"}, config={"configurable": {"thread_id": "..."}})
"""
