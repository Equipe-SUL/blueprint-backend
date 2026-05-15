# Engine CAD Determinística

Pipeline completo de extração de dados geométricos de arquivos DXF.

## Uso Programático

```python
from core.engine import process_dxf

# Uso básico
result = process_dxf("/caminho/para/planta.dxf")

# Uso com callback de progresso (opcional)
def meu_progresso(pct: float, msg: str):
    print(f"{pct*100:.0f}% — {msg}")

result = process_dxf("/caminho/para/planta.dxf",
                     progress_callback=meu_progresso)
```

# Verificar sucesso
print(result.success)      # True/False
print(result.error)        # mensagem de erro se falhou

# Métricas
m = result.metrics
print(f"Área total: {m.total_area:.2f} m²")
print(f"Perímetro total: {m.total_perimeter:.2f} m")

for room in m.rooms:
    print(f"  {room.area_m2:.2f}m² — perímetro {room.perimeter_m:.2f}m")

# Ambientes classificados
for room in result.rooms:
    print(f"  Nome: {room['nome_sugerido']}")

# Textos extraídos do DXF
for t in result.texts:
    print(f"  Texto: {t['texto']} — layer: {t['layer']}")

# Estatísticas
print(result.stats)
```

## Pipeline

```
DXF ──► Parser ──► IR ──► Flatten ──► Heal ──► Graph ──► Polygonize ──► Validate ──► Filter ──► Metrics ──► Classify
 ①       ②        ③        ④           ⑤       ⑥          ⑦              ⑧          ⑨         ⑩           ⑪
```

| Etapa | Módulo | Descrição |
|---|---|---|---|
| ① Leitura | `parser/dxf_parser.py` | Lê entidades do DXF: LINE, LWPOLYLINE, ARC, CIRCLE, TEXT, MTEXT, INSERT (blocos) |
| ② IR | `geometry/ir.py` | Representação interna: `Segment`, `Arc`, `Circle`, `Ring`, `Polygon`, `GeometryIR` |
| ③ Flatten | `geometry/curve_resolution.py` | Converte arcos e círculos em segmentos de reta (`flatten_curves`) |
| ④ Healing | `healing/healer.py` | Snap de vértices próximos + merge de segmentos duplicados |
| ⑤ Graph* | `topology/graph.py` | Grafo de adjacência (networkx) — **opcional**, pula se `CAD_SKIP_GRAPH=true` ou se segmentos > `CAD_BATCH_SIZE` |
| ⑥ Polygonize | `polygonization/polygonizer.py` | Detecta ciclos fechados no grafo → polígonos |
| ⑦ Validate | `polygonization/validation.py` | Valida e repara polígonos via shapely (`make_valid`, `buffer(0)`) |
| ⑧ Filter | `engine.py` | Remove polígonos com área < `CAD_MIN_AREA` |
| ⑨ Metrics | `metrics/engine.py` | Calcula área, perímetro e centroide de cada polígono |
| ⑩ Classify | `semantic/classifier.py` | Associa textos próximos aos polígonos para nomear ambientes |

## Estrutura de Dados

```python
@dataclass
class EngineResult:
    success: bool
    ir: Optional[GeometryIR]          # dados brutos do DXF
    segments: List[Segment]           # segmentos após flatten
    topology: Optional[TopologyGraph] # grafo de adjacência
    polygons: list                    # polígonos válidos
    metrics: Optional[MetricResult]   # áreas e perímetros
    rooms: List[dict]                 # ambientes classificados
    texts: List[dict]                 # textos extraídos
    error: Optional[str]              # mensagem de erro
    stats: dict                       # estatísticas do processamento
```

## Executar Testes

```bash
python core/tests/test_ir.py
python core/tests/test_healing.py
python core/tests/test_topology.py
python core/tests/test_polygonization.py
python core/tests/test_metrics.py
```

## Parâmetros Ajustáveis

Ver [CONFIGURACAO.md](CONFIGURACAO.md) para a lista completa de variáveis
(`CAD_EPSILON`, `CAD_SNAP_RADIUS`, `CAD_FLATTEN_EPSILON`, `CAD_MIN_AREA`,
`CAD_CLASSIFIER_MAX_DIST`).
