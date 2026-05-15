# Parâmetros Configuráveis

Todas as constantes da engine CAD são definidas em `core/config.py` e podem ser
sobrescritas via variáveis de ambiente no arquivo `.env`.

## Parâmetros Adaptativos

Além dos valores fixos definidos no `.env`, a engine ajusta automaticamente alguns
parâmetros de healing com base na escala real da geometria processada:

| Parâmetro | Fórmula adaptativa | Quando atua |
|---|---|---|
| `snap_radius` | `min(CAD_SNAP_RADIUS, median_segmentos * 0.1)` | Se a mediana dos segmentos for menor que `CAD_SNAP_RADIUS * 10` |
| `epsilon` | Mesmo valor do `snap_radius` adaptativo | Para manter coerência snap/merge |
| `min_area` | `min(CAD_MIN_AREA, (median_segmentos * 10)²)` | Se a escala da geometria for muito pequena |

Isso garante que a engine funcione corretamente em qualquer escala:

| Escala | Exemplo | `snap_radius` efetivo | `min_area` efetivo |
|---|---|---|---|
| Arquitetura (metros) | Planta baixa de 10×10m | `0.01` (config) | `0.01` (config) |
| Detalhe (milímetros) | Componente de 50×30mm | `~0.005` (adaptado) | `~0.000025` (adaptado) |
| Micro-escala (0.1mm) | Circuito integrado | `~1e-05` (adaptado) | `~1e-08` (adaptado) |
| Macro (quilômetros) | Mapa de 5×3km | `0.01` (config) | `0.01` (config) |

O ajuste é feito uma vez por chamada do `process_dxf`, baseado na mediana dos
primeiros 1000 segmentos após o flattening de curvas.

## Banco de Dados

| Variável | Padrão | Descrição |
|---|---|---|
| `DB_NAME` | `postgres` | Nome do banco PostgreSQL |
| `DB_USER` | `postgres` | Usuário do banco |
| `DB_PASSWORD` | vazio | Senha do banco |
| `DB_HOST` | `127.0.0.1` | Host do banco |
| `DB_PORT` | `5432` | Porta do banco |
| `DB_SSLMODE` | `disable` | Modo SSL (`require`, `disable`, `prefer`) |

## Engine CAD

Definidas em `CadConfig` no `core/config.py`:

| Variável | Padrão | Descrição |
|---|---|---|---|
| `CAD_EPSILON` | `0.001` | Tolerância geral para merge de segmentos duplicados. **Adaptativo**: reduzido automaticamente em geometrias de micro-escala |
| `CAD_SNAP_RADIUS` | `0.01` | Raio de snap para unificar vértices. **Adaptativo**: reduzido automaticamente para `median * 0.1` em geometrias muito pequenas |
| `CAD_FLATTEN_EPSILON` | `0.0001` | Precisão do achatamento de arcos/círculos em segmentos de reta |
| `CAD_MIN_AREA` | `0.01` | Área mínima (m²) para um polígono ser considerado ambiente útil. **Adaptativo**: reduzido automaticamente em geometrias de micro-escala |
| `CAD_CLASSIFIER_MAX_DIST` | `5.0` | Distância máxima (m) entre centroide e texto para nomear ambiente |
| `CAD_SKIP_GRAPH` | `false` | Pular grafo de topologia (networkx) — economiza memória em DXFs grandes |
| `CAD_BATCH_SIZE` | `50000` | Máximo de segmentos healed para construir o grafo. Acima disso, pula automaticamente |

### Exemplo de `.env`

```env
DB_NAME=blueprint
DB_USER=admin
DB_PASSWORD=secret123
DB_HOST=192.168.1.100
DB_PORT=5432

CAD_EPSILON=0.0001
CAD_SNAP_RADIUS=0.005
CAD_FLATTEN_EPSILON=0.00005
CAD_MIN_AREA=0.5
CAD_CLASSIFIER_MAX_DIST=3.0
```

### Como alterar

1. Edite o arquivo `.env` na raiz do projeto
2. Reinicie o servidor Django

Os valores são lidos uma vez na inicialização via `dotenv` e congelados na
dataclass `CadConfig` (imutável por ser `frozen=True`).
