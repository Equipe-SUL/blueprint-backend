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
```

## 4) Aplicar migracoes

```bash
python manage.py migrate
```

## 5) Rodar o servidor de desenvolvimento

```bash
python manage.py runserver
```

Servidor disponivel em: `http://127.0.0.1:8000/`

## Comandos uteis

Criar superusuario:

```bash
python manage.py createsuperuser
```

Desativar ambiente virtual:

```bash
deactivate
```