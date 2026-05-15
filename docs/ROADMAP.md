# Roadmap — Engine CAD Determinística

## Status Atual (13/05/2026)

| Categoria | Resultado |
|---|---|
| **Testes unitários** | ✅ **17/17** |
| **DXFs sintéticos extremos** | ✅ **80/80** (8 baterias de 10) |
| **DXFs reais da internet** | ✅ **8/8** (JSCAD, FreeCAD, ezdxf, eng90, filestar) |
| **DXF real do usuário** (teste.dxf) | ✅ **0 erros, 619 ambientes, 2462 m²** |
| **Django system check** | ✅ 0 issues |

**Total: 115/115 testes — zero crashes, zero surpresas.**

---

## Entidades Suportadas

| Entidade | Parse | Geometria extraída |
|---|---|---|
| `LINE` | ✅ Direto | Segmentos |
| `LWPOLYLINE` | ✅ Com bulges | Segmentos + Arcos |
| `POLYLINE` (R12/R2000+) | ✅ Com bulges + R12 implícito | Segmentos + Arcos |
| `ARC` | ✅ Direto | Arcos (flatten adaptativo) |
| `CIRCLE` | ✅ Direto | Círculos (flatten adaptativo) |
| `SPLINE` | ✅ Fit/Control points + numpy | Splines (flatten por Bezier) |
| `ELLIPSE` | ✅ Direto | Elipses (flatten paramétrico) |
| `HATCH` (PolylinePath) | ✅ Com bulges | Segmentos + Arcos |
| `HATCH` (EdgePath) | ✅ Line, Arc, Ellipse, Spline edges | Segmentos, Arcos, Elipses, Splines |
| `INSERT` | ✅ Aninhado + transforms acumulados | Geometria expandida com recursão guard |
| `TEXT` / `MTEXT` | ✅ Extração | Textos para classificação semântica |
| `DIMENSION` | ✅ Defpoints + texto | Segmentos das linhas de extensão + texto |
| `SOLID` | ✅ `wcs_vertices()` | Até 4 segmentos |
| `3DFACE` | ✅ `wcs_vertices()` | Até 4 segmentos |
| `LEADER` / `MULTILEADER` | ✅ Vértices | Segmentos conectados |
| `MLINE` | ✅ Vértices | Segmentos conectados |
| `POINT` | ✅ Parse + ignorar | — |
| `WIPEOUT` | ✅ Parse + ignorar | — |
| `MESH` | ✅ Parse + ignorar | — |
| `VIEWPORT` | ✅ Parse + ignorar | — |

## Entidades Ignoradas (sem warning)

`RAY`, `XLINE`, `VIEWPORT`, `MESH`, `POINT`, `ATTDEF`, `ATTRIB`,
`ACIS`, `BODY`, `REGION`, `SURFACE`, `UNDERLAY`, `XREF`, `LIGHT`,
`IMAGE`, `PDFUNDERLAY`, `DWFUNDERLAY`, `DGNUNDERLAY`,
`TABLE`, `TOLERANCE`, `OLEFRAME`, `OLE2FRAME`,
`SECTION`, `SUN`, `RTEXT`, `ARCTEXT`

---

## Recursos Implementados

| Recurso | Detalhes |
|---|---|
| **Parâmetros adaptativos** | `snap_radius`, `epsilon`, `flatten_epsilon`, `min_area` ajustam-se automaticamente à escala da geometria |
| **OCS** | Arbitrary Axis Algorithm via `ezdxf.math.OCS` |
| **Unidades** | Leitura `$INSUNITS`, conversão para metros (20 unidades) |
| **Layer filter** | `CAD_LAYER_WHITELIST` / `CAD_LAYER_BLACKLIST` |
| **Block nesting** | Acumulação de transforms (rotação + escala + translação + mirror) |
| **MAX_BLOCK_NESTING=50** | Proteção contra referências circulares entre blocos |
| **XREF resolution** | Busca `.dxf` no diretório do arquivo e carrega bloco externo |
| **Recover mode** | Fallback para `ezdxf.recover` em DXF corrompidos |
| **try-catch por entidade** | Erro em 1 entidade não derruba o DXF inteiro |
| **Adjacência entre ambientes** | `shapely.touches` |
| **Classifier por bounding box** | Textos dentro do polígono têm peso 2× |
| **GeoJSON exporter** | `core/exporters/geojson.py` |
| **Progress callback** | `progress_callback(pct, msg)` opcional |
| **Skip graph mode** | `CAD_SKIP_GRAPH=true` ou automático via `CAD_BATCH_SIZE` |
| **polygonize_full** | Diagnóstico de `dangles`, `cuts`, `invalid_rings` |
| **Filtro por área** | `CAD_MIN_AREA` adaptativo |
| **3D→2D projection** | Coordenadas Z ≠ 0 projetadas corretamente para 2D |
| **Paperspace ignorado** | Apenas ModelSpace é processado |

---

## Limitações Conhecidas

| Limitação | Impacto |
|---|---|
| **SVG exporter** — não implementado | Baixo (usar GeoJSON + ferramentas externas) |
| **Filtro por tipo de entidade** — não implementado | Baixo (usar layer filter) |
| **Override manual de unidades** — não implementado | Baixo (editar DXF original) |
| **DXF R9/anteriores** — não testado | Muito baixo (pré-1994, extremamente raro) |

---

## Sprints Concluídas

| Sprint | Status |
|---|---|
| **Sprint 1** — SPLINE, ELLIPSE, HATCH, try-catch, recover | ✅ |
| **Sprint 2** — polygonize_full, layer filter, nested INSERT | ✅ |
| **Sprint 3** — OCS, unidades | ✅ |
| **Sprint 4** — Adjacência, bounding box classifier, GeoJSON | ✅ |
| **Sprint 5** — DIMENSION, SOLID, 3DFACE, LEADER, MLINE | ✅ |
| **Sprint 6** — Testes de cobertura (binary, hatch edges, R12, XREF) | ✅ |
| **Sprint 7** — Performance (progress callback, skip graph) | ✅ |
| **Sprint 8** — XREF resolution + ACIS ignore | ✅ |
