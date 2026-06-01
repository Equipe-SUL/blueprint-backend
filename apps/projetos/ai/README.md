# Blueprint AI — Módulo de Processamento Inteligente

Pipeline de extração, análise e orçamentação de projetos de construção civil a partir de plantas DXF.

## Arquitetura

```
DXF Upload
    │
    ▼
┌─────────────────────┐
│    CAD Engine       │  (cad/)
│  parse → heal →     │
│  polygonize →       │
│  classify → metrics │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   dxf_core.py       │  (extracaocalculo/)
│  Extração           │
│  determinística     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    adapter.py       │  (services/)
│  CAD → Orçamento    │
│  format conversion  │
└──────┬──────┬───────┘
       │      │
       ▼      ▼
┌──────────┐ ┌──────────────────┐
│ Memorial │ │    Orçamento     │
│Descritivo│ │     SINAPI       │
│(grafo_   │ │                  │
│novo/)    │ │ sinapi_matcher   │
│          │ │  (keyword + LLM) │
│ pdf_     │ │                  │
│ generator│ │ orcamento_full_  │
│          │ │ service.py       │
│ descriti │ │ export_orcamento │
│ vo_      │ │  (.xlsx)         │
│ service  │ │                  │
└──────────┘ └──────────────────┘
```

## Estrutura de Diretórios

```
ai/
├── cad/                    # CAD Engine geométrico
│   ├── dxf_parser.py       # Parse de entidades DXF (linhas, arcos, blocos, textos)
│   ├── curve_resolution.py # Aplainamento de curvas em segmentos de reta
│   ├── healer.py           # Snap de vértices, merge de segmentos colineares
│   ├── polygonizer.py      # Grafo de adjacência → detecção de ciclos → polígonos
│   ├── validation.py       # Validação e reparo de anéis (winding, self-intersection)
│   ├── classifier.py       # Associação TXT_AMBIENTE → polígonos de cômodos
│   ├── text_rooms.py       # Fallback de detecção de cômodos por pares de texto
│   ├── metrics.py          # Cálculo de área, perímetro, matriz de adjacência
│   ├── topology.py         # Grafo topológico (NetworkX)
│   ├── structural_analysis.py # Análise de elementos estruturais
│   ├── ir.py               # Representação Intermediária (GeometryIR)
│   ├── geojson.py          # Geração de GeoJSON
│   └── engine.py           # Orquestrador principal
│
├── extracaocalculo/        # Extração determinística + exportação
│   ├── dxf_core.py         # Extração central com mapeamento estático de layers
│   └── dxf_exportadores.py # Exportação MemorialCalculo para JSON/CSV/PDF
│
├── grafo_novo/             # LangGraph pipeline (Memorial Descritivo)
│   ├── state_descritivo.py      # DescritivoState TypedDict
│   ├── nodes_descritivo.py      # 4 nós do grafo
│   ├── edges_descritivo.py      # Arestas condicionais
│   └── builder_descritivo.py    # Compilação do StateGraph
│
├── services/               # Camada de serviço da aplicação
│   ├── adapter.py               # Converte saída da extração para formato de orçamento
│   ├── descritivo_service.py    # Orquestrador: view → LangGraph (memorial)
│   ├── orcamento_service.py     # Matching SINAPI (keyword + LLM) + cálculo
│   ├── orcamento_full_service.py# Pipeline completo: DXF → CAD → adapter → SINAPI → XLSX
│   ├── export_orcamento.py      # Exportação .xlsx com openpyxl
│   └── pdf_generator.py         # Geração de PDF do memorial (reportlab)
│
├── rag/                    # Retrieval-Augmented Generation (ChromaDB)
│   ├── embeddings.py            # HuggingFace Embeddings (multilingual MiniLM)
│   ├── vectorstore.py           # Cliente Chroma para coleções SINAPI/NBRs
│   ├── ingest_referencia.py     # Ingestão da planilha SINAPI Referência
│   └── ingest_nbrs.py           # Ingestão de PDFs de normas técnicas
│
├── sinapi_matcher.py       # Filtro keyword + matching LLM contra tabela SINAPI
├── prompts_descritivo.py   # Prompts do sistema para o LLM auditor
├── nbrs.py                 # Integração RAG de NBRs nos prompts
├── client.py               # Cliente ChatOllama (singleton cacheado)
└── config.py               # Configuração centralizada
```

## Pipeline de Orçamento SINAPI

O fluxo completo (`orcamento_full_service.py`):

1. **CAD Engine** — Processa o DXF (parse, heal, polygonize, classify, metrics)
2. **dxf_core** — Extração determinística de quantitativos
3. **adapter** — Converte dados extraídos para formato padronizado de orçamento
4. **Análise estrutural** — Identifica elementos estruturais (vigas, pilares, lajes)
5. **Matching SINAPI** — `sinapi_matcher.py`: primeiro filtro por keyword, depois LLM para escolha exata
6. **Cálculo final** — Preço total = quantidade × preço SINAPI
7. **Persistência** — Cria `ItemProjeto` no banco (apenas itens com matching SINAPI)
8. **Exportação** — Gera `.xlsx` via `export_orcamento.py`

> **Importante:** O matching SINAPI **obriga** uso de LLM. Não há fallback silencioso para apenas keyword.

## Configuração

Todas as variáveis de ambiente relevantes:

| Variável | Padrão | Descrição |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do servidor Ollama |
| `OLLAMA_CHAT_MODEL` | `gemma4:31b-cloud` | Modelo para matching SINAPI |
| `OLLAMA_VL_MODEL` | `gemma4:31b-cloud` | Modelo para análise de imagem (se aplicável) |
| `OLLAMA_TEMPERATURE` | `0.1` | Temperatura do LLM |
| `LANGSMITH_TRACING` | `false` | Habilitar tracing LangSmith |

## Management Commands

```bash
# Ingerir dados SINAPI Referência no ChromaDB
python manage.py ingerir_referencia_sinapi --limpar

# Ingerir composições SINAPI (mão de obra)
python manage.py ingerir_sinapi

# Ingerir PDFs de normas técnicas (NBRs)
python manage.py ingerir_nbrs
```
