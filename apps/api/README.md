# Corelix - API Backend

API backend para Corelix — uma secretária inteligente com IA para profissionais autônomos de saúde e bem-estar.

## Stack

- **Framework:** FastAPI (async)
- **Language:** Python 3.11+
- **ORM:** SQLAlchemy 2.0 (async) + Alembic
- **Database:** PostgreSQL 16
- **Authentication:** JWT + Refresh Tokens
- **AI:** Anthropic Claude API
- **WhatsApp:** Meta Cloud API (Embedded Signup)
- **Job Queue:** pgqueuer (PostgreSQL-based)
- **Tests:** pytest + pytest-asyncio + httpx + factory-boy

## Pré-requisitos

- Python 3.11 ou superior
- Poetry (gerenciador de dependências)
- Docker e Docker Compose (para PostgreSQL local)
- PostgreSQL 16 (ou use Docker)

## Setup Inicial

### 1. Instalar Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Instalar dependências

```bash
cd apps/api
poetry install
```

### 3. Configurar variáveis de ambiente

```bash
# Na raiz do monorepo (application/)
cp .env.example .env
```

Edite `.env` e preencha os valores necessários:

```env
# Obrigatórios para desenvolvimento local
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/secretaria_digital_dev
SECRET_KEY=<gere com: openssl rand -hex 32>
ANTHROPIC_API_KEY=<sua chave da Anthropic>
ENCRYPTION_KEY=<gere com Python: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())>
```

### 4. Iniciar PostgreSQL (Docker)

```bash
# Na raiz do monorepo
docker-compose up -d
```

Verifique se o banco está rodando:

```bash
docker-compose ps
```

### 5. Executar migrações

```bash
cd apps/api
poetry run alembic upgrade head
```

### 6. Rodar a aplicação

```bash
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em:
- **API:** http://localhost:8000
- **Docs (Swagger):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Testes

### Rodar todos os testes

```bash
poetry run pytest
```

### Rodar com cobertura

```bash
poetry run pytest --cov=. --cov-report=html
```

Abra `htmlcov/index.html` no navegador para ver o relatório de cobertura.

### Rodar testes de um módulo específico

```bash
poetry run pytest tests/auth/
poetry run pytest tests/clients/test_service.py
```

### Rodar com logs detalhados

```bash
poetry run pytest -v -s
```

## Migrações de Banco de Dados

### Criar uma nova migração

```bash
poetry run alembic revision --autogenerate -m "descrição da migração"
```

### Aplicar migrações

```bash
poetry run alembic upgrade head
```

### Reverter última migração

```bash
poetry run alembic downgrade -1
```

### Ver histórico de migrações

```bash
poetry run alembic history
```

## Estrutura do Projeto

```
apps/api/
├── auth/               # Autenticação e autorização
├── professionals/      # Gestão de profissionais
├── clients/           # Gestão de clientes
├── agenda/            # Agendamentos e disponibilidade
├── reports/           # Relatórios e insights
├── whatsapp/          # Integração WhatsApp
├── ai/                # Serviços de IA (Claude)
├── core/              # Configuração, database, exceptions
│   ├── config.py      # Settings via Pydantic
│   ├── database.py    # SQLAlchemy engine + RLS
│   ├── exceptions.py  # Custom exceptions
│   └── security.py    # JWT, bcrypt (a implementar)
├── tests/             # Testes organizados por módulo
├── alembic/           # Migrações do banco
├── main.py            # Entry point da aplicação
└── pyproject.toml     # Dependências e configuração
```

Cada módulo segue a arquitetura de 3 camadas:
- `router.py` — Endpoints HTTP (FastAPI)
- `service.py` — Lógica de negócio
- `repository.py` — Acesso ao banco de dados
- `schemas.py` — Validação Pydantic (entrada/saída)

## Arquitetura Multi-Tenant

Este projeto usa **Row-Level Security (RLS)** do PostgreSQL para isolar dados entre profissionais (tenants).

### Como funciona:

1. Cada requisição autenticada define o contexto do tenant:
   ```python
   await set_tenant_context(db, professional_id)
   ```

2. PostgreSQL aplica automaticamente filtros RLS em todas as queries

3. O contexto é local à transação e limpa automaticamente ao final

### Regra importante:
**Sempre** chamar `set_tenant_context()` após obter a sessão do banco e antes de qualquer query em dados de tenant.

## Desenvolvimento

### Linters e Formatação

```bash
# Formatar código
poetry run black .

# Verificar qualidade do código
poetry run ruff check .

# Type checking
poetry run mypy .
```

### Convenções

- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, etc)
- **Idioma do código:** Inglês
- **Idioma da documentação:** Português
- **Type hints:** Obrigatório em todas as funções
- **Async/await:** Obrigatório em todo código assíncrono
- **TDD:** Escrever teste antes da implementação

## Health Check

Verifique se a API está saudável:

```bash
curl http://localhost:8000/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "environment": "development",
  "database": "connected"
}
```

## Troubleshooting

### Erro: "Connection refused" ao conectar ao banco

Verifique se o Docker está rodando:
```bash
docker-compose ps
```

Reinicie o container se necessário:
```bash
docker-compose restart postgres
```

### Erro: "Port 5432 already in use"

Você tem PostgreSQL rodando localmente. Opções:
1. Pare o PostgreSQL local: `brew services stop postgresql` (macOS)
2. Mude a porta no `docker-compose.yml`: `"5433:5432"`
3. Use o PostgreSQL local e ajuste a `DATABASE_URL` no `.env`

### Erro: "ModuleNotFoundError"

Certifique-se de estar no ambiente virtual do Poetry:
```bash
poetry shell
```

Ou prefixe comandos com `poetry run`:
```bash
poetry run uvicorn main:app --reload
```

### Testes falhando com erro de banco

Recrie o banco de testes:
```bash
docker-compose down -v
docker-compose up -d
poetry run alembic upgrade head
```

## Recursos

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Poetry Docs](https://python-poetry.org/docs/)

## License

Proprietary - Corelix © 2024
