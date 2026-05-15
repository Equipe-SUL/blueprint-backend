# API REST

Base URL: `http://localhost:8080/api/`

---

## `GET /api/server/`

Health check. Retorna o status do servidor.

**Resposta:** `200 OK`
```
Servidor está ativo
```

---

## `GET/POST /api/projetos/`

CRUD de projetos (DRF ViewSet padrão).

**GET** — Lista todos os projetos.
**POST** — Cria um novo projeto.

---

## `GET/POST /api/projetos/{id}/upload/`

Upload de arquivo DXF ou Excel para um projeto.

**GET** — Lista arquivos enviados para o projeto.
**POST** — Envia um arquivo (multipart/form-data).

### Parâmetros POST

| Campo | Tipo | Obrigatório |
|---|---|---|
| `arquivo` | file | Sim |

### Extensões aceitas

- `.dxf` → processado pela engine CAD (`core.engine.process_dxf`)
- `.xls` / `.xlsx` → processado pelo parser Excel (pandas)

### Resposta (DXF, 201 Created)

```json
{
  "arquivo": {
    "id": 1,
    "nome_original": "planta.dxf",
    "caminho_arquivo": "/media/uploads/1/planta.dxf",
    "tamanho_mb": 0.82,
    "status_processamento": "processado",
    "data_upload": "2026-05-13T00:00:00"
  },
  "itens_extraidos": {
    "ambientes": [
      {
        "nome": "SALA",
        "area_m2": "20.0",
        "perimetro_m": "18.0",
        "centroid": {"x": 2.0, "y": 2.5}
      }
    ],
    "textos_legenda": [
      {"texto": "SALA", "layer": "TEXTOS"}
    ],
    "quantidades_por_etiqueta": [],
    "geometria": {
      "segmentos": 42,
      "topologia_vertices": 30,
      "topologia_arestas": 42,
      "poligonos_encontrados": 5,
      "area_total_calculada_m2": 100.0,
      "perimetro_total_calculado_m": 50.0
    }
  }
}
```

---

## `GET/POST /api/projetos/{id}/itens/`

CRUD de itens (materiais/serviços) de um projeto.

**GET** — Lista itens do projeto.
**POST** — Cria um ou mais itens.

### POST (cadastro manual — objeto único)

```json
{
  "descricao_original": "Cabo 10mm",
  "unidade": "m",
  "quantidade": 150.0
}
```

### POST (importação IA — lista)

```json
[
  {
    "descricao_original": "Disjuntor 40A",
    "unidade": "un",
    "quantidade": 5,
    "catalogo": 123
  }
]
```

---

## `POST /api/projetos/{id}/teste-planilha/`

Teste de extração de planilha Excel (.xls/.xlsx). Não persiste dados.

---

## `POST /api/projetos/{id}/arquivos/{arquivo_id}/interpretar/`

Interpreta os dados extraídos do DXF usando IA (LLM) para classificar itens
e sugerir composições SINAPI.

**Resposta:** `200 OK`
```json
{
  "projeto_id": 1,
  "arquivo_id": 2,
  "nome_arquivo": "planta.dxf",
  "ai": { ... }
}
```

---

## Limites

| Recurso | Limite |
|---|---|
| Tamanho máximo de arquivo | 15 MB |
| Formatos aceitos | .dxf, .xls, .xlsx |
