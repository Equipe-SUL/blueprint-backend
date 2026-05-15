# PRD — Refatoração Arquitetural do Blueprint para Engine CAD Determinística

## Projeto

- Frontend: https://github.com/Equipe-SUL/Blueprint
- Backend: https://github.com/Equipe-SUL/blueprint-backend

---

# 1. Introdução

## 1.1 Contexto

O projeto Blueprint atualmente possui como objetivo interpretar arquivos CAD/DXF para realizar cálculos arquitetônicos, extração de ambientes e análise estrutural de plantas.

Após análise detalhada do backend, foi identificado que o sistema atual não implementa uma engine geométrica determinística para interpretação CAD.

O pipeline atual depende majoritariamente de:

- extração de entidades TEXT/MTEXT;
- regex sobre anotações humanas;
- inferência visual via VLM;
- heurísticas semânticas;
- planilhas intermediárias.

Isso significa que o sistema atual:

- não reconstrói topologia geométrica;
- não calcula áreas geometricamente;
- não interpreta entidades fundamentais do DXF;
- não possui engine CAD real;
- depende de textos escritos manualmente no desenho.

---

# 2. Problema Central

## 2.1 Problema Arquitetural

O Blueprint atualmente trata arquivos DXF como documentos textuais/visuais.

Porém:

```text
DXF != documento textual
DXF = estrutura geométrica + topológica
```

O sistema atual ignora completamente a estrutura geométrica do CAD.

---

# 3. Diagnóstico Técnico Atual

---

# 3.1 O sistema não interpreta geometria CAD

## Evidência

O backend atualmente utiliza:

```python
msp.query('TEXT MTEXT')
```

mas não processa:

- LINE
- ARC
- LWPOLYLINE
- POLYLINE
- SPLINE
- HATCH
- INSERT
- BLOCK
- REGION

---

## Consequências

O sistema:

- não entende paredes;
- não entende contornos;
- não entende ambientes;
- não entende conectividade;
- não entende regiões;
- não entende curvas;
- não entende topologia.

---

# 3.2 O sistema não calcula áreas

## Estado Atual

Hoje o backend apenas extrai:

```text
"12m²"
"P=14m"
```

via regex em entidades TEXT/MTEXT.

---

## Consequências

As métricas:

- dependem de anotação manual;
- podem estar incorretas;
- podem estar desatualizadas;
- não possuem validação geométrica;
- quebram em desenhos sem labels.

---

# 3.3 Dependência excessiva de VLM/LLM

## Estado Atual

O backend utiliza:

- MiniCPM-V;
- Ollama;
- inferência visual;
- heurísticas semânticas.

---

## Problema

LLMs/VLMs:

- não possuem precisão geométrica;
- não preservam invariantes topológicos;
- não garantem consistência matemática;
- não possuem determinismo;
- hallucinam conectividade.

---

## Consequências

Erros tornam-se inevitáveis em:

- plantas grandes;
- CADs industriais;
- múltiplos pavimentos;
- geometrias curvas;
- blocos complexos;
- desenhos com ruído.

---

# 3.4 O sistema descarta geometria CAD

## Evidência encontrada

O backend possui lógica que explicitamente ignora:

- arco;
- círculo;
- polilinha;
- hachura;
- spline.

---

## Impacto

O sistema descarta exatamente as entidades fundamentais necessárias para reconstrução geométrica.

---

# 3.5 Ausência de pipeline topológica

Hoje não existe:

- polygonização;
- graph reconstruction;
- topology validation;
- geometric healing;
- region solving;
- loop solving;
- adjacency graph.

---

## Consequência

O sistema não consegue:

- fechar polígonos;
- detectar ambientes;
- detectar holes;
- validar regiões;
- resolver conectividade.

---

# 3.6 Ausência de suporte real ao DXF

## Funcionalidades fundamentais não suportadas

- bulges;
- nested blocks;
- INSERT;
- transforms;
- splines;
- hatch boundaries;
- unit normalization;
- UCS;
- curve flattening.

---

# 4. Objetivo da Refatoração

Transformar o Blueprint de:

```text
CAD Metadata Extractor
```

para:

```text
Deterministic CAD Geometry Engine
```

---

# 5. Objetivos Funcionais

O novo sistema deverá:

- interpretar geometria DXF real;
- reconstruir topologia;
- detectar ambientes automaticamente;
- calcular áreas geometricamente;
- calcular perímetros geometricamente;
- suportar CADs complexos;
- suportar blocos;
- suportar curvas;
- suportar plantas reais;
- reduzir dependência humana;
- utilizar IA apenas semanticamente.

---

# 6. Arquitetura Proposta

---

# 6.1 Pipeline Global

```text
DXF
 ↓
DXF Parser
 ↓
Geometry IR
 ↓
Block Expansion
 ↓
Curve Resolution
 ↓
Geometric Healing
 ↓
Topology Graph
 ↓
Polygonization
 ↓
Region Validation
 ↓
Metric Engine
 ↓
Optional Semantic AI
```

---

# 7. Camadas da Nova Arquitetura

---

# 7.1 Layer 1 — DXF Parsing

## Objetivo

Leitura determinística do arquivo DXF.

---

## Tecnologia Principal

### ezdxf

Responsável apenas por:

- parsing;
- leitura de entidades;
- acesso ao modelspace;
- acesso aos blocks.

---

## Entidades obrigatórias

### Fase inicial

- LINE
- ARC
- CIRCLE
- LWPOLYLINE
- POLYLINE
- INSERT

### Fase avançada

- SPLINE
- HATCH
- ELLIPSE
- REGION

---

# 7.2 Layer 2 — Geometry IR

## Objetivo

Transformar entidades DXF em representação geométrica uniforme.

---

## Estruturas recomendadas

```python
@dataclass
class Segment:
    start: Vec2
    end: Vec2

@dataclass
class Arc:
    center: Vec2
    radius: float
    start_angle: float
    end_angle: float

@dataclass
class Polyline:
    segments: list

@dataclass
class Polygon:
    outer: Ring
    holes: list[Ring]
```

---

## Benefícios

- desacoplamento do DXF;
- pipeline estável;
- testes independentes;
- arquitetura extensível.

---

# 7.3 Layer 3 — Block Expansion

## Problema Atual

INSERT/BLOCK não são tratados.

---

## Objetivo

Explodir:

- INSERT;
- nested blocks;
- transformed entities.

---

## Requisitos

Suporte a:

- rotação;
- escala;
- translation matrix;
- nested blocks.

---

# 7.4 Layer 4 — Curve Resolution

## Problema Atual

Bulges, splines e curvas não são tratados.

---

## Objetivo

Converter:

- bulges;
- splines;
- arcs;
- ellipses

em representação geométrica precisa.

---

## Estratégia

### Flattening adaptativo

Exemplo:

```text
epsilon = 0.1mm
```

---

# 7.5 Layer 5 — Geometric Healing

## Problema

CADs reais possuem:

- gaps;
- duplicatas;
- ruído numérico;
- linhas quase conectadas.

---

## Objetivo

Implementar:

- snapping;
- merge;
- deduplication;
- epsilon topology.

---

## Regra

```python
if distance(a, b) < epsilon:
    merge(a, b)
```

---

# 7.6 Layer 6 — Topology Graph

## Objetivo

Reconstruir conectividade geométrica.

---

## Estrutura

```text
vertices = nodes
segments = edges
```

---

## Tecnologias

- networkx
- shapely
- GEOS

---

# 7.7 Layer 7 — Polygonization

## Objetivo

Converter loops fechados em polígonos válidos.

---

## Tecnologia

### shapely.ops.polygonize

---

## Resultado esperado

- ambientes;
- regiões;
- contornos válidos;
- holes.

---

# 7.8 Layer 8 — Region Validation

## Objetivo

Validar:

- self-intersections;
- invalid rings;
- degenerate polygons;
- open loops.

---

## Estratégias

- GEOS validation;
- polygon repair;
- buffer(0).

---

# 7.9 Layer 9 — Metric Engine

## Objetivo

Calcular:

- área;
- perímetro;
- comprimento linear;
- centroid;
- adjacência.

---

## Requisitos

100% determinístico.

Nenhuma métrica pode depender de:

- TEXT;
- MTEXT;
- OCR;
- LLM.

---

# 7.10 Layer 10 — Semantic AI Layer

## Objetivo

Utilizar IA apenas semanticamente.

---

## IA pode auxiliar em:

- classificação de cômodos;
- OCR;
- interpretação arquitetônica;
- identificação de símbolos;
- nomeação automática.

---

## IA NÃO pode participar de:

- cálculo geométrico;
- fechamento de loops;
- conectividade;
- cálculo de áreas;
- topologia.

---

# 8. Tecnologias Recomendadas

| Tecnologia | Objetivo |
|---|---|
| Python | Orquestração |
| ezdxf | Parsing DXF |
| shapely | Geometria |
| GEOS | Kernel geométrico |
| numpy | Vetores |
| networkx | Topologia |

---

# 9. Estrutura Proposta de Pastas

```text
core/
 ├── parser/
 ├── geometry/
 ├── topology/
 ├── healing/
 ├── polygonization/
 ├── metrics/
 ├── semantic/
 ├── exporters/
 └── tests/
```

---

# 10. Invariantes Arquiteturais

---

# 10.1 Regra Fundamental

```text
Geometria sempre precede semântica
```

---

# 10.2 Regras obrigatórias

## Nunca usar IA para:

- cálculo;
- geometria;
- topologia;
- fechamento de loops;
- conectividade.

---

## Toda geometria deve passar por:

- healing;
- topology validation;
- polygonization.

---

## Nenhuma métrica pode depender de TEXT/MTEXT.

---

# 11. Roadmap Técnico

---

# Fase 1 — Geometry Foundation

## Objetivos

- parsing real;
- Geometry IR;
- suporte a entidades básicas.

---

## Entregas

- LINE;
- POLYLINE;
- ARC;
- INSERT.

---

# Fase 2 — Healing & Topology

## Objetivos

- snapping;
- merge;
- graph reconstruction;
- topology validation.

---

# Fase 3 — Polygonization

## Objetivos

- ambientes;
- holes;
- region solving.

---

# Fase 4 — Deterministic Metrics

## Objetivos

- área;
- perímetro;
- adjacência;
- centroid.

---

# Fase 5 — Semantic Layer

## Objetivos

- classificação;
- OCR;
- identificação semântica.

---

# 12. Critérios de Sucesso

## Funcionais

O sistema deverá:

- calcular áreas sem labels;
- detectar ambientes automaticamente;
- suportar blocos;
- suportar curvas;
- suportar CADs reais;
- operar sem regex em TEXT.

---

## Não-funcionais

- deterministic output;
- reproducibilidade;
- tolerância numérica;
- escalabilidade;
- modularidade.

---

# 13. Riscos Técnicos

| Risco | Mitigação |
|---|---|
| DXFs inconsistentes | healing geométrico |
| Gaps numéricos | epsilon topology |
| CADs grandes | spatial indexing |
| Curvas complexas | flattening adaptativo |
| Performance | otimização incremental |

---

# 14. Referências Técnicas Fundamentais

Esta seção define as bibliotecas, engines geométricas, papers e documentações que deverão orientar diretamente a implementação da nova arquitetura.

Essas referências não são complementares.

Elas representam o núcleo técnico necessário para transformar o Blueprint em uma engine CAD determinística real.

---

# 14.1 ezdxf

## Repositório

https://github.com/mozman/ezdxf

---

## Documentação

https://ezdxf.readthedocs.io/en/stable/

---

## Responsabilidade no Projeto

O ezdxf deverá ser utilizado exclusivamente como:

- parser DXF;
- leitor de entidades;
- acesso ao modelspace;
- acesso a blocks;
- acesso a transforms;
- acesso aos metadados do desenho.

---

## O que NÃO deve ser responsabilidade do ezdxf

O ezdxf NÃO deverá:

- resolver topologia;
- fechar polígonos;
- calcular ambientes;
- validar geometria;
- resolver conectividade.

Essas responsabilidades pertencem à nova pipeline geométrica.

---

## Entidades obrigatórias a serem suportadas

### Fase 1

- LINE
- ARC
- CIRCLE
- LWPOLYLINE
- POLYLINE
- INSERT

### Fase 2

- SPLINE
- ELLIPSE
- HATCH
- REGION

---

## Documentação crítica

### LWPOLYLINE

https://ezdxf.mozman.at/docs/dxfentities/lwpolyline.html

---

## Importância crítica

A documentação de LWPOLYLINE é fundamental porque:

```text
LWPOLYLINE != sequência de linhas
```

Ela pode conter:

- bulges;
- arcos implícitos;
- curvas.

O sistema atual ignora completamente isso.

---

## Implementação esperada

### Parsing principal

```python
for entity in msp:
    dxftype = entity.dxftype()
```

---

## Estratégia obrigatória

Toda entidade DXF deverá ser convertida para:

```text
Geometry IR
```

antes de qualquer cálculo.

---

# 14.2 Shapely

## Documentação

https://shapely.readthedocs.io/en/stable/

---

## Responsabilidade no Projeto

O Shapely será o núcleo principal da geometria computacional.

Será responsável por:

- polygonização;
- operações booleanas;
- união geométrica;
- validação;
- snapping;
- merge;
- métricas.

---

## Operações obrigatórias

### polygonize

```python
from shapely.ops import polygonize
```

Responsável por:

- transformar segmentos em polígonos válidos;
- detectar ambientes;
- detectar regiões fechadas.

---

### unary_union

```python
from shapely.ops import unary_union
```

Responsável por:

- unir segmentos;
- normalizar geometrias;
- resolver overlaps.

---

### linemerge

```python
from shapely.ops import linemerge
```

Responsável por:

- fundir segmentos conectados;
- simplificar topologia.

---

### snap

```python
from shapely.ops import snap
```

Responsável por:

- healing geométrico;
- correção de gaps;
- snapping tolerante.

---

### validation

```python
geometry.is_valid
```

Responsável por:

- detectar self intersections;
- detectar polygons inválidos;
- validar loops.

---

## Pipeline recomendada com Shapely

```text
segments
 ↓
healing
 ↓
linemerge
 ↓
unary_union
 ↓
polygonize
 ↓
validation
 ↓
metrics
```

---

# 14.3 GEOS

## Website oficial

https://libgeos.org/

---

## Papel no Projeto

GEOS será o kernel geométrico subjacente.

Shapely opera sobre GEOS.

---

## Responsabilidades

- predicates geométricos;
- operações topológicas;
- validação;
- polygon repair;
- interseções;
- union.

---

## Importância

GEOS é utilizado por:

- PostGIS;
- QGIS;
- GDAL;
- Shapely.

Isso significa que o Blueprint passará a utilizar a mesma classe de engine geométrica utilizada em GIS/CAD profissional.

---

# 14.4 CGAL

## Website

https://www.cgal.org/

---

## Documentação crítica

### Polygon Repair

https://doc.cgal.org/latest/Polygon_repair/index.html

---

## Importância no Projeto

O CGAL deverá servir como referência arquitetural para:

- healing geométrico;
- polygon repair;
- reconstrução topológica;
- planar arrangements;
- face labeling.

---

## Problemas que o CGAL resolve

- loops quebrados;
- polygons inválidos;
- self intersections;
- vértices duplicados;
- geometria inconsistente.

---

## Estratégia recomendada

Mesmo que o projeto não utilize diretamente CGAL inicialmente, sua arquitetura deverá seguir os mesmos princípios:

```text
entrada inválida
 ↓
reconstrução topológica
 ↓
polígono válido
```

---

## Migração futura

Caso a engine Python torne-se insuficiente:

- CGAL poderá ser utilizado via C++;
- ou via bindings;
- ou como geometry core separado.

---

# 14.5 Polygon Repair — Estratégia Obrigatória

## Conceito

Todo CAD real possui:

- gaps;
- floating point noise;
- segmentos quase conectados;
- loops degenerados;
- geometrias inválidas.

---

## O sistema deverá implementar

### Epsilon topology

```python
EPSILON = 0.001
```

---

### Snap tolerance

```python
if distance(a, b) < EPSILON:
    merge(a, b)
```

---

## Objetivo

Garantir:

- fechamento de loops;
- estabilidade topológica;
- polygonização robusta.

---

# 14.6 Planar Graph Reconstruction

## Problema Atual

O sistema atual não possui representação topológica.

---

## Objetivo

Transformar geometria em:

```text
nodes + edges
```

antes de:

- ambientes;
- regiões;
- áreas.

---

## Estrutura esperada

```python
class TopologyGraph:
    vertices
    edges
    adjacency
```

---

## Biblioteca recomendada

### networkx

https://networkx.org/

---

## Uso esperado

- adjacency graph;
- loop solving;
- region traversal;
- connectivity analysis.

---

# 14.7 OpenCascade (Longo Prazo)

## Website

https://www.opencascade.com/

---

## Papel futuro

Caso o Blueprint evolua para:

- CAD industrial;
- BIM;
- 3D;
- B-Rep;
- sólidos;
- modelagem paramétrica;

OpenCascade deverá ser estudado.

---

## Importância

OpenCascade é utilizado por:

- FreeCAD;
- kernels CAD industriais;
- softwares CAM.

---

# 15. Estratégia Arquitetural Definitiva

---

# 15.1 Regra principal

```text
Geometria primeiro
Semântica depois
```

---

# 15.2 Pipeline obrigatória

```text
DXF
 ↓
ezdxf
 ↓
Geometry IR
 ↓
Block expansion
 ↓
Curve flattening
 ↓
Healing
 ↓
Topology graph
 ↓
Polygonization
 ↓
Validation
 ↓
Deterministic metrics
 ↓
Optional semantic AI
```

---

# 15.3 IA deve ser opcional

IA poderá auxiliar apenas em:

- classificação;
- OCR;
- identificação semântica;
- sugestões.

---

## IA NÃO poderá participar de:

- cálculo geométrico;
- conectividade;
- polygonização;
- fechamento de loops;
- métricas.

---

# 16. Resultado Esperado

Após a refatoração, o Blueprint deixará de ser:

```text
um extrator heurístico de textos CAD
```

para se tornar:

```text
uma engine geométrica determinística para interpretação DXF
```

capaz de:

- interpretar CADs reais;
- produzir métricas confiáveis;
- operar sem labels manuais;
- escalar para projetos complexos;
- utilizar IA apenas como camada semântica complementar.

