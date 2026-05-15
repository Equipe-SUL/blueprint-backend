# Blueprint Backend

Sistema de extração inteligente de dados de projetos de engenharia/arquitetura a partir de arquivos DXF.

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                   Django App                     │
│  apps/projetos/                                  │
│  ├── views/          ← endpoints REST            │
│  ├── services/       ← lógica de extração        │
│  ├── ai/             ← interpretação por LLM     │
│  └── models.py       ← ORM (Projeto, Item, etc)  │
└──────────────┬──────────────────────────────────┘
               │ chama
┌──────────────▼──────────────────────────────────┐
│         Core CAD Engine (determinístico)          │
│  core/                                            │
│  ├── engine.py          ← orquestrador principal  │
│  ├── config.py          ← parâmetros ajustáveis   │
│  ├── parser/dxf_parser  ← leitura de DXF          │
│  ├── geometry/          ← IR + curva -> segmentos │
│  ├── healing/           ← snap + merge de vértices│
│  ├── topology/          ← grafo de adjacência     │
│  ├── polygonization/    ← fechamento de polígonos │
│  ├── metrics/           ← área, perímetro         │
│  └── semantic/          ← classificação por texto │
└──────────────────────────────────────────────────┘
```

## Documentação

| Documento | O que contém |
|---|---|---|
| [`PRD_IA_SEMANTICA.md`](../.prd/prd_ia_semantica.md) | PRD da camada de IA semântica (classificação, orçamento, anomalias) |
| [`PRD_IMPLEMENTACAO.md`](PRD_IMPLEMENTACAO.md) | Mapeamento PRD → implementação (10 camadas) |
| [`CONFIGURACAO.md`](CONFIGURACAO.md) | Parâmetros configuráveis (.env) |
| [`API.md`](API.md) | Endpoints REST da API |
| [`ENGINE.md`](ENGINE.md) | Como usar a engine CAD standalone |
| [`AMBIENTE.md`](AMBIENTE.md) | Setup do ambiente de desenvolvimento |
