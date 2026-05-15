# Ambiente de Desenvolvimento

## Pré-requisitos

- Python 3.12+
- PostgreSQL (via Docker ou instalado localmente)
- pip / venv

## Setup

```bash
# 1. Criar virtualenv
python -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Subir PostgreSQL com Docker
docker run -d --name postgres18 \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 5432:5432 \
  postgres:18

# 4. Configurar variáveis de ambiente
cp .env.example .env   # ou criar manualmente (ver CONFIGURACAO.md)

# 5. Rodar migrations
python manage.py migrate

# 6. Iniciar servidor
python manage.py runserver
```

## Banco Local (alternativa sem Docker)

```bash
# Instalar PostgreSQL no sistema
sudo apt install postgresql
sudo systemctl start postgresql

# Criar banco
sudo -u postgres createdb blueprint
```

## Comandos Úteis

```bash
# Verificar se o Django está OK
python manage.py check

# Testar health check
curl http://localhost:8080/api/server/

# Rodar testes da engine CAD
python core/tests/test_metrics.py

# Rodar todos os testes da engine
for f in core/tests/test_*.py; do python "$f"; done

# Shell interativo do Django
python manage.py shell
```

## Estrutura do Projeto

```
blueprint-backend/
├── .env                      # variáveis de ambiente
├── manage.py                 # entrypoint Django
├── requirements.txt          # dependências Python
├── setup/
│   ├── settings.py           # configurações Django
│   └── urls.py               # roteamento principal
├── core/                     # engine CAD determinística
│   ├── engine.py
│   ├── config.py
│   ├── geometry/
│   ├── healing/
│   ├── topology/
│   ├── polygonization/
│   ├── metrics/
│   ├── semantic/
│   ├── parser/
│   └── tests/
├── apps/
│   └── projetos/
│       ├── models.py
│       ├── serializers.py
│       ├── urls.py
│       ├── services/
│       ├── views/
│       └── ai/
├── docs/                     # documentação
├── .prd/                     # PRD original
└── media/                    # uploads (gitignored)
```

## Dependências Principais

| Pacote | Uso |
|---|---|
| Django + DRF | Framework web e API REST |
| ezdxf | Leitura de arquivos DXF |
| networkx | Grafo de topologia |
| shapely | Validação e reparo de polígonos |
| pandas | Leitura de planilhas Excel |
| langchain + ollama | IA para interpretação de itens |
| psycopg2 | Conexão PostgreSQL |
