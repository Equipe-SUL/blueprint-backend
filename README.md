# Blueprint Backend

## Requisitos

- Python 3.11+ instalado
- PostgreSQL disponível (local ou remoto)

## 1) Criar e ativar ambiente virtual (venv)

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear scripts, execute uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Windows (CMD)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Instalar dependencias dentro do Ambiente Virtual

```bash
pip install -r requirements.txt
```

## 3) Configurar variaveis de ambiente

Crie o arquivo `.env` a partir do exemplo:

### Windows

```powershell
copy .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Preencha o `.env` com os dados do PostgreSQL:

```env
DB_NAME=seu_banco
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_SSLMODE=disable
```

Para Supabase ou outro banco remoto com TLS, use `DB_SSLMODE=require` e o host remoto.

## 4) Aplicar migracoes

```bash
python manage.py migrate
```

## 5) Rodar o servidor de desenvolvimento

```bash
python manage.py runserver
```

Servidor disponivel em: `http://127.0.0.1:8000/`

## 6) Ingerir dados SINAPI (ChromaDB)

O pipeline de orçamento depende de uma base vetorial ChromaDB com os dados SINAPI.
Execute os comandos abaixo na ordem:

```bash
# Ingerir planilha de referência SINAPI (~4.820 itens)
python manage.py ingerir_referencia_sinapi --limpar

# Ingerir composições de mão de obra
python manage.py ingerir_sinapi
```

> O ChromaDB é armazenado localmente em `chroma_db/` (~76 MB) e está no `.gitignore` — cada desenvolvedor precisa rodar a ingestão ao clonar o projeto.

### NBRs (normas técnicas — opcional)

Caso queira enriquecer o memorial descritivo com normas técnicas:

1. Crie a pasta `nbrs/` na raiz do backend
2. Coloque os PDFs das NBRs desejadas
3. Execute:

```bash
python manage.py ingerir_nbrs
```

## Comandos uteis

Criar superusuario:

```bash
python manage.py createsuperuser
```

Desativar ambiente virtual:

```bash
deactivate
```