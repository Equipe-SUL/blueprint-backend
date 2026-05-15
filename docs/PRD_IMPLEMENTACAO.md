# Implementação do PRD — Engine CAD Determinística

Documento que mapeia o [PRD original](../.prd/prd_refatoracao_blueprint_engine_cad_deterministica%20(1).md)
para a implementação real, camada por camada.

---

## Pipeline vs Implementação

```
PRD                                             Implementação
─────                                           ─────────────
Layer 1  — DXF Parsing         ──►  core/parser/dxf_parser.py
Layer 2  — Geometry IR         ──►  core/geometry/ir.py
Layer 3  — Block Expansion     ──►  incluso no dxf_parser.py (INSERT → explode)
Layer 4  — Curve Resolution    ──►  core/geometry/curve_resolution.py
Layer 5  — Geometric Healing   ──►  core/healing/healer.py
Layer 6  — Topology Graph      ──►  core/topology/graph.py
Layer 7  — Polygonization      ──►  core/polygonization/polygonizer.py
Layer 8  — Region Validation   ──►  core/polygonization/validation.py
Layer 9  — Metric Engine       ──►  core/metrics/engine.py
Layer 10 — Semantic AI         ──►  core/semantic/classifier.py
                                    apps/projetos/ai/
```

---

## Layer 1 — DXF Parsing

**Arquivo:** `core/parser/dxf_parser.py`
**PRD §7.1**

Lê todas as entidades obrigatórias da Fase 1 do PRD:

| Entidade | Status | Detalhes |
|---|---|---|
| `LINE` | ✅ | Convertido para `Segment` |
| `LWPOLYLINE` | ✅ | Com suporte a bulges (arcos implícitos) |
| `POLYLINE` | ✅ | Vertex list → Segment |
| `ARC` | ✅ | Raio, ângulos, sentido |
| `CIRCLE` | ✅ | Centro + raio |
| `INSERT` | ✅ | Explode blocos aninhados com rotação/escala |

Também extrai `TEXT` / `MTEXT` para classificação semântica posterior.

### Blocos (INSERT)

O parser suporta:
- Blocos aninhados (INSERT dentro de INSERT)
- Transformações: rotação, escala X/Y, translação
- Entidades dentro de blocos: LINE, LWPOLYLINE, ARC, CIRCLE, TEXT

**Parâmetros relacionados:** nenhum (leitura pura)

---

## Layer 2 — Geometry IR

**Arquivo:** `core/geometry/ir.py`
**PRD §7.2**

Representação interna desacoplada do DXF. Dataclasses puras:

| Classe | Campos | Uso |
|---|---|---|
| `Segment` | `start: Vec2`, `end: Vec2` | Linhas e arestas poligonais |
| `Arc` | `center, radius, start_angle, end_angle, ccw` | Arcos (curvas) |
| `Circle` | `center, radius` | Círculos |
| `Ring` | `vertices: List[Vec2]` | Contorno fechado |
| `Polygon` | `outer: Ring`, `holes: List[Ring]` | Polígono com buracos |
| `GeometryIR` | `segments, arcs, circles, texts` | Contêiner do IR completo |

**PRD §7.2 — Estruturas recomendadas:** Implementado exatamente como proposto.

---

## Layer 3 — Block Expansion

**Arquivo:** `core/parser/dxf_parser.py` (função `_parse_insert`)
**PRD §7.3**

Processa entidades `INSERT`:
- Obtém o block definition do DXF
- Itera sobre as entidades dentro do bloco
- Aplica transformação: rotação + escala X/Y + translação para cada entidade
- Blocos aninhados são resolvidos recursivamente

**Parâmetros relacionados:** nenhum

---

## Layer 4 — Curve Resolution (Flattening)

**Arquivo:** `core/geometry/curve_resolution.py`
**PRD §7.4**

Converte `Arc` e `Circle` em segmentos de reta aproximados.

### Algoritmo

```python
num_segments = abs_sweep / acos(1 - epsilon / radius)
```

O número de segmentos é adaptativo: quanto menor o raio ou maior o `epsilon`,
menos segmentos são gerados.

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_FLATTEN_EPSILON` | `0.0001` | Menor ε → mais segmentos, maior precisão |
| `CAD_EPSILON` | `0.001` | Raio mínimo para gerar segmentos |

---

## Layer 5 — Geometric Healing

**Arquivo:** `core/healing/healer.py`
**PRD §7.5**

Corrige imperfeições comuns de CADs reais.

### Etapas

1. **Snap** (`_snap_vertices`): agrupa vértices dentro de `snap_radius` em um único ponto
2. **Merge** (`_merge_duplicates`): remove segmentos duplicados (mesmo par start/end)

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_SNAP_RADIUS` | `0.01` | Maior raio → mais snapping, pode deformar geometrias pequenas |
| `CAD_EPSILON` | `0.001` | Tolerância para detectar segmentos duplicados |

### Exemplo

```python
# Se snap_radius = 0.05, estes dois segmentos viram um:
seg1 = Segment(Vec2(0, 0), Vec2(1, 0.005))
seg2 = Segment(Vec2(0, 0), Vec2(1, 0))
# Após snap: Segment(Vec2(0,0), Vec2(1,0)) — duplicata removida
```

---

## Layer 6 — Topology Graph

**Arquivo:** `core/topology/graph.py`
**PRD §7.6**

Constrói grafo de adjacência (`networkx.Graph`):

```
vértices = nodes
segmentos = edges (não-direcionados)
```

### Funcionalidades

- `from_segments(segments)` → constrói grafo
- `node_count()` / `edge_count()` → estatísticas
- Grafo não-direcionado (arestas não têm orientação)

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_EPSILON` | `0.001` | Usado no healing antes da construção do grafo |

---

## Layer 7 — Polygonization

**Arquivo:** `core/polygonization/polygonizer.py`
**PRD §7.7**

Converte segmentos healed em polígonos fechados.

### Tecnologia

Usa `shapely.ops.polygonize` para detectar ciclos fechados.

### Entrada

Lista de `Segment` (após healing) — formando um grafo planar.

### Saída

Lista de `Polygon` (IR) com:
- `outer: Ring` — contorno externo
- `holes: List[Ring]` — buracos internos

Se um polígono tiver buracos, eles são detectados via
`shapely.ops.polygonize_full` (dangles, cuts, holes).

### Parâmetros relacionados

Nenhum direto, mas snapping (`CAD_SNAP_RADIUS`) e epsilon (`CAD_EPSILON`)
afetam drasticamente a qualidade da polygonização.

---

## Layer 8 — Region Validation

**Arquivo:** `core/polygonization/validation.py`
**PRD §7.8**

Valida e repara polígonos usando Shapely/GEOS.

### Pipeline de validação

```
Polygon IR
  → Shapely Polygon
  → is_valid? → make_valid() se inválido
  → MultiPolygon? → pega o de maior área
  → is_empty ou area < 1e-10? → descarta
  → Polygon IR válido
```

### Estratégias implementadas

| Estratégia PRD | Implementação |
|---|---|
| GEOS validation | ✅ `shapely.is_valid` |
| Polygon repair | ✅ `shapely.make_valid` |
| `buffer(0)` | ✅ fallback se `make_valid` falhar |
| Self-intersection | ✅ `make_valid` corrige |
| Degenerate polygons | ✅ Filtro por `min_area` (Layer 9) |

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_MIN_AREA` | `0.01` | Remove polígonos degenerados (hatch, text boxes, etc) |

---

## Layer 9 — Metric Engine

**Arquivo:** `core/metrics/engine.py`
**PRD §7.9**

Cálculo 100% determinístico de métricas geométricas.

### Métricas calculadas

| Métrica | Fonte | Unidade |
|---|---|---|
| `area_m2` | `shapely.Polygon.area` | m² |
| `perimeter_m` | `shapely.Polygon.length` | m |
| `centroid_x` | `shapely.Polygon.centroid.x` | m |
| `centroid_y` | `shapely.Polygon.centroid.y` | m |

### Filtro de área (Redução de Geometrias)

Após a polygonização, muitos polígonos pequenos são gerados a partir de:

- Hachuras (HATCH) — contornos de preenchimento
- Text boxes — caixas de texto que formam mini-polígonos
- Mobília — blocos de móveis que formam ciclos fechados
- Cotas — linhas de dimensão que se fecham
- Símbolos — tags, setas, detalhes de anotação

O filtro de área remove esses polígonos antes do cálculo de métricas e
classificação, garantindo que apenas ambientes reais sejam considerados.

**Arquivo:** `core/engine.py` — função `_filter_by_area()`
**Algoritmo:** Shoelace formula (área exata do polígono)

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_MIN_AREA` | `0.01` | **Área mínima em m².** Reduza para capturar ambientes muito pequenos (ex: 0.001 para shafts). Aumente para ignorar ruído (ex: 0.5 para plantas industriais) |

**Exemplo prático:**
```
CAD_MIN_AREA=0.01 → 1108 polígonos → 455 ambientes úteis (filtrou 653 mini-polígonos)
CAD_MIN_AREA=0.50 → 1108 polígonos → ~200 ambientes (apenas cômodos reais)
CAD_MIN_AREA=0.001 → 1108 polígonos → ~800 ambientes (inclui shafts e nichos)
```

---

## Layer 10 — Semantic AI

**Arquivos:** `core/semantic/classifier.py`, `apps/projetos/ai/`
**PRD §7.10**

Camada puramente semântica. A IA **não** participa de:

- ❌ Cálculo geométrico
- ❌ Conectividade
- ❌ Polygonização
- ❌ Fechamento de loops
- ❌ Métricas

### Classificador (core/semantic/classifier.py)

Associa textos próximos aos polígonos para nomear ambientes.

**Algoritmo:**
```
Para cada polígono:
  1. Calcula centroide
  2. Encontra o texto mais próximo (distância euclidiana)
  3. Se distância < CAD_CLASSIFIER_MAX_DIST, usa o texto como nome
  4. Senão, nomeia como "Ambiente N"
```

### Parâmetros

| Variável | Padrão | Efeito |
|---|---|---|
| `CAD_CLASSIFIER_MAX_DIST` | `5.0` | Distância máxima (m) entre centroide e texto. Aumente para plantas com textos longe dos ambientes. Reduza para evitar falsos positivos |

### IA Interpretativa (apps/projetos/ai/)

Usa LLM (Ollama + LangChain) para:
- Classificar itens extraídos em categorias SINAPI
- Sugerir composições de custo
- Estruturar dados para orçamento

---

## Invariantes Arquiteturais

### PRD §10 — Regra Fundamental

```text
Geometria sempre precede semântica
```

✅ A pipeline executa 9 camadas geométricas antes de qualquer processamento
semântico/IA.

### PRD §10.2 — IA nunca para geometria

| Proibido | Situação atual |
|---|---|
| IA para cálculo | ✅ `core/metrics/` é puramente geométrico |
| IA para topologia | ✅ `core/topology/` usa networkx |
| IA para fechamento de loops | ✅ `core/polygonization/` usa shapely |
| IA para conectividade | ✅ `core/healing/` é determinístico |

### PRD §12 — Critérios de Sucesso

| Critério | Status |
|---|---|
| Calcular áreas sem labels | ✅ |
| Detectar ambientes automaticamente | ✅ |
| Suportar blocos | ✅ |
| Suportar curvas | ✅ |
| Suportar CADs reais | ✅ (testado com **8 DXFs reais da internet** + **80 extremos sintéticos** + DXF do usuário) |
| Operar sem regex em TEXT | ✅ |
| Deterministic output | ✅ |
| Reproducibilidade | ✅ (mesmo DXF + mesmos parâmetros = mesmo resultado) |
| Tolerância numérica | ✅ |
| Modularidade | ✅ (10 camadas = 10 diretórios) |

---

## Roadmap Futuro (PRD §11)

| Fase | Status | Pendências |
|---|---|---|
| Fase 1 — Geometry Foundation | ✅ Completo | — |
| Fase 2 — Healing & Topology | ✅ Completo | — |
| Fase 3 — Polygonization | ✅ Completo | — |
| Fase 4 — Deterministic Metrics | ✅ Completo | — |
| Fase 5 — Semantic Layer | ✅ Completo (classificador) | LLM interpretativo em progresso |
| SPLINE / ELLIPSE / HATCH | ✅ Completo | — |
| DIMENSION / SOLID / 3DFACE / LEADER / MLINE | ✅ Completo | — |
| OCS / Unidades / Layer filter | ✅ Completo | — |
| Recover / try-catch / skip_graph / progress | ✅ Completo | — |
| XREF resolution / nested blocks | ✅ Completo | — |
| **80 extremos sintéticos + 8 reais** | ✅ **88/88 DXFs processados** | — |
