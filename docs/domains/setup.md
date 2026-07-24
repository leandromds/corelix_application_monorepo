# Domain: Setup e Ambiente Local

---

## Pré-requisitos

| Ferramenta | Versão mínima | Propósito |
|---|---|---|
| Docker + Docker Compose | 24.x | PostgreSQL local |
| Python | 3.11+ | Backend |
| Poetry | 1.8+ | Gerenciamento de deps Python |
| Node.js | 20.x (LTS) | Frontend |
| npm | 10.x | Deps frontend |

---

## Estrutura do Monorepo

```
application/
├── apps/
│   ├── api/          → Backend Python + FastAPI
│   └── web/          → Frontend React + TypeScript + Vite
├── docker-compose.yml
├── .env.example
└── docs/             → Documentação estruturada (este diretório)
```

---

## Setup Inicial (primeira vez)

### 1. Clonar e configurar variáveis de ambiente

```bash
git clone <repo>
cd application

# Copiar e editar o .env
cp .env.example .env
# Editar .env com os valores reais (ver seção Variáveis de Ambiente abaixo)
```

### 2. Subir o PostgreSQL via Docker

```bash
docker-compose up -d

# Verificar se está saudável
docker-compose ps
# Aguardar status "healthy" antes de continuar
```

### 3. Criar o banco de testes

```bash
docker exec secretaria-digital-db psql -U postgres -c \
  "CREATE DATABASE secretaria_digital_test;"
```

### 4. Criar o role para testes de RLS (ADR-021)

```bash
docker exec secretaria-digital-db psql -U postgres -d secretaria_digital_test -c "
  CREATE ROLE test_rls_user NOLOGIN;
  GRANT USAGE ON SCHEMA public TO test_rls_user;
  GRANT ALL ON ALL TABLES IN SCHEMA public TO test_rls_user;
  GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO test_rls_user;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO test_rls_user;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO test_rls_user;
"
```

### 5. Instalar dependências Python

```bash
cd apps/api
poetry install
```

### 6. Rodar as migrations

```bash
cd apps/api
poetry run alembic upgrade head
```

### 7. Instalar dependências frontend

```bash
cd apps/web
npm install
```

---

## Rodar o Projeto Localmente

### Backend (API)

```bash
cd apps/api
poetry run uvicorn main:app --reload --port 8000
```

API disponível em: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`
Health check: `http://localhost:8000/health`

### Frontend (Vite dev server)

```bash
cd apps/web
npm run dev
```

Frontend disponível em: `http://localhost:5173`

O Vite está configurado com proxy: requests para `/api/*` são redirecionados para `http://localhost:8000`.
Isso garante que os cookies `samesite=strict` funcionam corretamente em desenvolvimento.

---

## Rodar os Testes

```bash
cd apps/api

# Todos os testes
poetry run pytest tests/ -v

# Sem coverage (mais rápido durante desenvolvimento)
poetry run pytest tests/ -v --no-cov

# Módulo específico
poetry run pytest tests/auth/ -v

# Arquivo específico
poetry run pytest tests/clients/test_router.py -v

# Teste específico por nome
poetry run pytest tests/auth/test_service.py -k "test_login" -v
```

### Relatório de cobertura

```bash
poetry run pytest tests/ --cov=. --cov-report=html
# Abre htmlcov/index.html no browser
```

---

## Variáveis de Ambiente

### Backend (`apps/api/.env`)

```bash
# Banco de dados
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/secretaria_digital
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/secretaria_digital_test

# JWT
SECRET_KEY=<string aleatória de 64+ chars — nunca commitar o valor real>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Ambiente
ENVIRONMENT=development

# CORS (separado por vírgula)
ALLOWED_ORIGINS=http://localhost:5173

# IA
AI_API_KEY=<chave do provider OpenAI-compatible: OpenAI, OpenRouter, DeepSeek, Groq, etc.>
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# WhatsApp
WHATSAPP_VERIFY_TOKEN=<token arbitrário para verificação do webhook>
```

> Gerar `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(64))"`

### Frontend (`apps/web/.env`)

```bash
# URL base da API — em dev usa o proxy do Vite
VITE_API_URL=/api/v1
```

> Em produção, `VITE_API_URL` deve ser a URL completa: `https://api.corelix.com.br/api/v1`

---

## Docker Compose

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    container_name: secretaria-digital-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: secretaria_digital
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

---

## Migrations com Alembic

```bash
cd apps/api

# Ver status atual das migrations
poetry run alembic current

# Aplicar todas as migrations pendentes
poetry run alembic upgrade head

# Criar uma nova migration (detecta diferenças no modelo)
poetry run alembic revision --autogenerate -m "descricao_da_mudanca"

# Rollback de uma migration
poetry run alembic downgrade -1

# Ver histórico de migrations
poetry run alembic history
```

> **Atenção:** migrations geradas por `--autogenerate` **não incluem** políticas RLS.
> Policies RLS devem ser adicionadas manualmente ao arquivo de migration após a geração.
> Ver `alembic/versions/56f1e41b5d4c_initial_schema.py` como referência.

---

## Linting e Type Checking

```bash
cd apps/api

# Linting com ruff
poetry run ruff check .

# Autofix
poetry run ruff check . --fix

# Type checking com mypy
poetry run mypy .
```

```bash
cd apps/web

# Type checking TypeScript
npm run type-check
# ou
npx tsc --noEmit

# Build de produção (inclui type check)
npm run build
```

---

## Estrutura de Arquivos Relevantes

```
apps/api/
├── alembic/
│   ├── env.py                  → async-compatible migration environment
│   ├── script.py.mako          → template para arquivos de migration
│   └── versions/
│       └── 56f1e41b5d4c_initial_schema.py  → migration inicial (aplicada)
├── tests/
│   └── conftest.py             → fixtures globais de teste
├── main.py                     → app FastAPI: CORS, lifespan, exception handlers, /health
├── pyproject.toml              → deps Poetry + config ruff/mypy/pytest
└── .env                        → variáveis de ambiente (nunca commitar)

apps/web/
├── src/
│   └── services/
│       └── api.ts              → instância axios com interceptors
├── vite.config.ts              → proxy /api → localhost:8000
├── .env                        → VITE_API_URL=/api/v1
└── tsconfig.json
```

---

## Fluxo de Desenvolvimento Diário

```bash
# 1. Atualizar develop
git checkout develop && git pull origin develop

# 2. Criar branch da feature
git checkout -b feature/nome-da-feature

# 3. Subir o banco (se não estiver rodando)
docker-compose up -d

# 4. Rodar testes antes de começar (baseline verde)
cd apps/api && poetry run pytest tests/ --no-cov -q

# 5. Desenvolver com TDD (Red → Green → Refactor)
# 6. Rodar testes com frequência durante o desenvolvimento

# 7. Antes de abrir PR: garantir que todos os testes passam
poetry run pytest tests/ -v --no-cov

# 8. Push e PR
git push origin feature/nome-da-feature
```

---

## Troubleshooting

### `AttributeError: module 'bcrypt' has no attribute '__about__'`
bcrypt instalado em versão 4.x+. Rodar `poetry install` novamente — o lock file
fixa `bcrypt < 4` (ADR-013).

### Cookie de refresh token não chega no browser
Verificar `ENVIRONMENT=development` no `.env` — com `production`, o cookie `secure=True`
é rejeitado pelo browser em HTTP (ADR-017).

### `SET LOCAL app.current_tenant` — erro em testes de RLS
O role `test_rls_user` não foi criado no banco de teste. Executar o script de setup da
seção "Criar o role para testes de RLS" acima (ADR-021).

### Erro de CORS no browser (403 ou blocked)
Verificar `ALLOWED_ORIGINS` no `.env` — deve incluir `http://localhost:5173` exatamente,
sem trailing slash (ADR-018).

### `ProgrammingError: syntax error at or near "$1"` em `SET LOCAL`
Tentativa de usar bind params em `SET LOCAL`. Ver ADR-008 — usar f-string com UUID validado.

### Migrations não incluem políticas RLS
Normal — Alembic `--autogenerate` não detecta policies. Adicionar manualmente ao arquivo
de migration. Ver `56f1e41b5d4c_initial_schema.py` como modelo.