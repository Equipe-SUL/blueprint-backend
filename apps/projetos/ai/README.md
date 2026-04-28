# Blueprint Backend - Módulo de IA

Orquestração de IA para análise de plantas arquitetônicas e geração de documentos técnicos.

## Visão Geral

A camada de IA está separada em responsabilidades bem definidas, seguindo princípios SOLID:

- **Configuração**: variáveis de ambiente e credenciais centralizadas.
- **Cliente LLM**: interface única para o modelo (Ollama ou outro).
- **Retrieval (RAG)**: indexação e busca semântica em base vetorial.
- **Tools**: funções que o agente pode chamar (extrair dados de DXF, contexto do projeto, normas).
- **Agents**: orquestração de fluxos por domínio (alvenaria, elétrica, etc.).
- **Orchestration**: grafo de estados e transições (LangGraph).
- **Tracing**: observabilidade via LangSmith.

## Estrutura de Pastas

```
apps/projetos/ai/
├── __init__.py                 # Exports públicos
├── config.py                   # Config centralizada (env vars, defaults)
├── client.py                   # Cliente LLM (ChatOllama com cache)
├── prompts.py                  # Templates de prompts
│
├── rag/                        # Retrieval-Augmented Generation
│   ├── __init__.py
│   ├── documents.py            # Transformar fontes → Document objects
│   ├── embeddings.py           # Fábrica de embeddings
│   ├── vectorstore.py          # Chroma (persistência, search)
│   └── retriever.py            # Interface de recuperação (com tracing)
│
├── tools/                      # Funções chamáveis pelo agente
│   ├── __init__.py
│   ├── dxf.py                  # Adaptar saída de parsing DXF
│   ├── project_context.py      # Buscar dados do projeto (DB)
│   └── standards.py            # Acesso a normas e templates técnicos
│
├── agents/                     # Agentes especializados por domínio
│   ├── __init__.py
│   ├── base.py                 # Contrato/interface comum
│   └── alvenaria.py            # Agente específico (alvenaria)
│
├── orchestration/              # LangGraph: grafo de estados
│   ├── __init__.py
│   ├── state.py                # Definição do estado do grafo
│   └── graph.py                # Montagem de nós e arestas
│
└── services/                   # Camada de aplicação (chamada por views)
    ├── __init__.py
    └── alvenaria_service.py    # Expõe interface pública para Django
```

## Fluxo Completo

```
1. Upload (API) → Extração DXF determinística (services.py, fora de AI)
                 ↓
2. Chamada da IA (alvenaria_service.py)
                 ↓
3. Grafo LangGraph inicia (orchestration/graph.py)
   ├─ Node "retrieve": retriever busca normas em Chroma
   ├─ Node "generate": LLM gera rascunho com contexto
   ├─ Node "validate": valida contra regras (estruturado)
   └─ Node "persist": salva no DB
                 ↓
4. Retorna resultado estruturado para API
                 ↓
5. (Opcional) LangSmith traça cada passo (com @traceable)
```