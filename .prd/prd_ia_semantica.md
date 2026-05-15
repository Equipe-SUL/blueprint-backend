# PRD — Camada de IA Semântica

## Objetivo

Adicionar inteligência artificial à camada semântica do Blueprint, aproveitando os
dados **já extraídos deterministicamente** pela engine CAD para gerar valor de
negócio: classificação inteligente de ambientes, orçamento automático, detecção
de anomalias e enriquecimento de dados.

## Princípios

1. **Geometria nunca depende de IA** — toda a pipeline geométrica (parser,
   healing, polygonization, metrics) permanece 100% determinística.
2. **IA só opera sobre dados já extraídos** — a IA consome o `EngineResult` e
   os métricas, nunca participa do cálculo geométrico.
3. **Resultado determinístico é o fallback** — se a IA falhar ou estiver
   indisponível, o sistema retorna os nomes/classificações determinísticas.

---

## Feature 1 — Classificador Inteligente de Ambientes

### Problema

O classificador atual (`core/semantic/classifier.py`) usa apenas distância
euclidiana entre centroide e texto. Limitações:

- Abreviações não são expandidas (`"COZ"` ≠ `"Cozinha"` na saída)
- Textos com erros ou parciais (`"SALA DE"`) viram nomes incompletos
- Ambientes sem texto próximo viram `"Ambiente N"`
- Nomes não são padronizados (`"SALA 01"`, `"Sala 1"`, `"sala"` são tratados
  como diferentes)

### Solução

Pipeline de classificação em 3 estágios:

```
EngineResult.polygons + texts
        │
        ▼
  [Estágio 1 — Normalização]
  LLM: "COZ" → "Cozinha"
       "DORM 01" → "Quarto 01"
       "SALA DE REUNIÃO" → "Sala de Reunião"
       "BWC" → "Banheiro"
        │
        ▼
  [Estágio 2 — Atribuição]
  Polígono + texto mais próximo + metadados
  LLM: decide o nome final baseado em:
    - texto normalizado do estágio 1
    - área e perímetro do polígono
    - adjacências (vizinhos)
    - proporção (largura/altura)
        │
        ▼
  [Estágio 3 — Ambientes sem texto]
  LLM: infere nome baseado em:
    - área (ex: < 3m² = Banheiro/Depósito)
    - proporção (ex: corredor = alongado)
    - adjacências (ex: ao lado da cozinha = despensa)
```

### Fallback

Se a LLM estiver indisponível, o classificador determinístico atual
(`_find_best_text`) é usado — garantindo que o sistema nunca quebre.

### Dados de entrada da LLM

```json
{
  "poligono": {
    "area_m2": 12.5,
    "perimetro_m": 14.0,
    "largura": 4.0,
    "altura": 3.125,
    "centroid_x": 5.0,
    "centroid_y": 6.0
  },
  "texto_proximo": "DORM",
  "textos_normalizados": ["Dormitório", "Quarto"],
  "vizinhos": [
    {"nome": "Circulação", "area_m2": 3.0},
    {"nome": "Banheiro", "area_m2": 2.5}
  ]
}
```

### Prompt sugerido

```
Dado um polígono de uma planta baixa com as seguintes características:
- Área: {area}m²
- Perímetro: {perimetro}m  
- Proporção (largura/altura): {proporcao}
- Texto mais próximo: "{texto_bruto}"
- Vizinhos identificados: {vizinhos}

Qual é o nome mais provável deste ambiente?
Responda apenas com o nome, sem explicações.
Considere: Sala, Quarto, Cozinha, Banheiro, Corredor, Varanda,
Depósito, Escritório, Área de Serviço, Garagem, Hall, Copa,
Despensa, Sacada, Lavabo, Suíte, Closet.
```

---

## Feature 2 — Orçamento Automático por Ambiente

### Problema

Atualmente o sistema extrai métricas geométricas (área, perímetro) mas não
as traduz em quantitativos de obra (m² de piso, m de rodapé, etc.). O usuário
precisa fazer essa conversão manualmente.

### Solução

Para cada ambiente detectado, a IA gera uma lista de itens de orçamento
baseada no tipo do ambiente + suas métricas:

```
Sala 20m² (perímetro 18m)
  → Piso vinílico: 20 m²
  → Rodapé: 18 m
  → Tinta parede: 56 m² (perímetro × altura_padrão)
  → Tomada: 2 unidades (regra: 1 a cada 10m²)
  → Interruptor: 1 unidade
  → Lâmpada LED: 2 unidades (regra: 1 a cada 10m²)

Banheiro 4m²
  → Piso cerâmico: 4 m²
  → Parede cerâmica: 20 m² (perímetro × 2.5m - vãos)
  → Vaso sanitário: 1 unidade
  → Lavatório: 1 unidade
  → Chuveiro: 1 unidade
  → Teto PVC: 4 m²
```

### Implementação

```
[RoomClassifier] → ambiente nomeado + métricas
        │
        ▼
[QuantificationRules] → regras por tipo de ambiente
  - Regras fixas (vaso sanitário = 1 por banheiro)
  - Regras paramétricas (piso = area_m2)
  - Regras proporcionais (1 tomada a cada 10m²)
        │
        ▼
[LLM Refinement] → opcional, ajusta quantidades
  baseado em anomalias ou casos não-padrão
```

### Fallback

Regras paramétricas puras (sem LLM) para ambientes padrão. LLM só é
consultada para casos ambíguos ou quando as regras não cobrem.

---

## Feature 3 — Detecção de Anomalias

### Problema

A engine processa qualquer DXF deterministicamente, mas não valida se o
resultado faz sentido arquitetonicamente.

### Solução

Pipeline de validação semântica pós-processamento:

```
EngineResult
  │
  ├─ [Validator: Adjacência]
  │  Detecta ambientes sem acesso (grau 0 no grafo)
  │  → "Sala 15m² não tem nenhum ambiente adjacente"
  │
  ├─ [Validator: Proporção]
  │  Detecta ambientes com forma anômala
  │  → "Banheiro 50m² — área muito grande para banheiro"
  │  → "Sala proporção 1:20 (2m × 40m) — forma suspeita"
  │
  ├─ [Validator: Sobreposição]
  │  Detecta polígonos que se sobrepõem (via shapely.intersects)
  │  → "Ambiente 3 e Ambiente 7 se sobrepõem em 2.5m²"
  │
  └─ [Validator: Nome vs Métricas]
     IA valida se nome condiz com métricas
     → "Depósito 0.5m² — muito pequeno para depósito"
     → "Quarto 2m² — área insuficiente para cama"
```

### Saída

```json
{
  "anomalias": [
    {
      "tipo": "sem_acesso",
      "severidade": "alta",
      "ambiente": "Sala 15m²",
      "mensagem": "Ambiente sem nenhum vizinho adjacente"
    },
    {
      "tipo": "proporcao_invalida",
      "severidade": "media",
      "ambiente": "Banheiro index=7",
      "mensagem": "50m² — área muito grande para banheiro (esperado 2-6m²)"
    }
  ],
  "total_anomalias": 2,
  "score_qualidade": 0.85
}
```

---

## Feature 4 — Enriquecimento da Interpretação (expansão)

### Problema

O `interpretation.py` atual classifica itens de texto em composições SINAPI,
mas ignora os dados geométricos disponíveis.

### Solução

Alimentar a IA de interpretação com dados geométricos + textuais:

```
Entrada atual:
  "textos_legenda": [{"texto": "CABO 10mm", "layer": "ELÉTRICA"}]

Entrada expandida:
  "textos_legenda": [{"texto": "CABO 10mm", "layer": "ELÉTRICA"}]
  "ambientes": [{"nome": "Sala", "area_m2": 20}],
  "geometria": {"area_total": 150, "poligonos": 8}
```

Isso permite que a IA deduza, por exemplo:
- "50m de cabo 10mm numa sala de 20m² → provavelmente 2.5m/m²"
- "8 poligonos detectados → 8 ambientes para orçar"

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                   core/ (determinístico)                 │
│  parser → flatten → heal → graph → polygonize → metrics  │
└────────────────────────┬────────────────────────────────┘
                         │ EngineResult
                         ▼
┌─────────────────────────────────────────────────────────┐
│              apps/projetos/ai/ (semântico)                │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────────┐         │
│  │ ClassifierAI     │  │ QuantificationEngine │         │
│  │ (normaliza nomes)│  │ (gera quantitativos)  │         │
│  └────────┬─────────┘  └──────────┬───────────┘         │
│           │                       │                      │
│  ┌────────▼───────────────────────▼───────────┐         │
│  │           AnomalyDetector                    │         │
│  │  (valida adjacência, proporção, nomes)       │         │
│  └────────┬───────────────────────┬───────────┘         │
│           │                       │                      │
│  ┌────────▼─────────┐  ┌─────────▼────────────┐        │
│  │ InterpretationAI │  │  Orchestrator        │         │
│  │ (SINAPI/RAG)     │  │  (coordena fluxo)    │         │
│  └──────────────────┘  └──────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### Fluxo de dados

```
EngineResult
  → ClassifierAI → RoomResults (nomes limpos)
  → QuantificationEngine → BudgetItems (quantitativos)
  → AnomalyDetector → AnomalyReport (validação)
  → InterpretationAI → SINAPIResults (itens classificados)
  → Orchestrator → Resposta consolidada
```

---

## Critérios de Sucesso

| Critério | Métrica |
|---|---|
| Precisão do classificador de ambientes | >90% nomes corretos em planta real |
| Cobertura de abreviações | >95% das abreviações comuns expandidas |
| Quantitativos gerados automaticamente | Erro <10% vs orçamento manual |
| Anomalias detectadas | >80% das anomalias reais identificadas |
| Latência total da IA | <5s para planta de até 50 ambientes |
| Fallback sem IA | 100% funcional (nomes determinísticos) |

---

## Roadmap de Implementação

| Fase | Features | Esforço |
|---|---|---|
| **Fase 1** | ClassifierAI (normalização + atribuição) | Alto |
| **Fase 2** | QuantificationEngine (regras + LLM) | Alto |
| **Fase 3** | AnomalyDetector (validação semântica) | Médio |
| **Fase 4** | InterpretationAI expandida (geo + texto) | Baixo |
| **Fase 5** | Orchestrator + testes integrados | Médio |

---

## Riscos

| Risco | Mitigação |
|---|---|
| LLM alucina nomes de ambiente | Fallback determinístico + validação por área |
| Custo de tokens muito alto | Cache de resultados + batch processing |
| Latência alta (múltiplas chamadas LLM) | Paralelismo via `asyncio.gather` |
| Qualidade dependente do modelo | Suporte a múltiplos provedores (Ollama, OpenAI) |
