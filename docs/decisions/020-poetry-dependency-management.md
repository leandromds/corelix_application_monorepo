# 020 - Poetry para Gerenciamento de Dependências Python

**Status:** `accepted`

---

## Context

O projeto Python precisa de um sistema de gerenciamento de dependências que garanta:
- Builds reproduzíveis em qualquer máquina (dev, CI, Railway)
- Separação clara entre dependências de produção e desenvolvimento
- Configuração centralizada (sem múltiplos arquivos de config espalhados)
- Compatibilidade com o ambiente de deploy (Railway)

As alternativas consideradas foram `pip` + `requirements.txt`, `pip-tools`, e `Poetry`.

## Decision

Usar **Poetry** com `pyproject.toml` como única fonte de verdade para dependências e
configuração de ferramentas Python.

### Estrutura do `pyproject.toml`

```toml
[tool.poetry]
name = "corelix-api"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.110"
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
alembic = "^1.13"
pydantic-settings = "^2.0"
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
bcrypt = ">=3.2,<4"          # fixado — passlib incompatível com bcrypt 4.x+ (ADR-013)
python-jose = {extras = ["cryptography"], version = "^3.3"}
httpx = "^0.27"
anthropic = "^0.25"
pgqueuer = "^0.1"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
pytest-postgresql = "^5.0"
factory-boy = "^3.3"
ruff = "^0.4"
mypy = "^1.9"

[tool.ruff]
line-length = 88
select = ["E", "F", "I"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

## Rationale

**Por que Poetry (e não pip + requirements.txt)?**

| Critério | pip + requirements.txt | Poetry |
|----------|------------------------|--------|
| Lock file determinístico | Apenas com `pip-compile` extra | Nativo (`poetry.lock`) |
| Separação prod / dev | Dois arquivos (`requirements.txt` + `requirements-dev.txt`) | Um arquivo, grupos declarativos |
| Configuração centralizada | `setup.cfg` ou `setup.py` separados | Tudo em `pyproject.toml` |
| Resolução de conflitos de versão | Manual | Automática com backtracking |
| Detecção por Railway | Requer `Procfile` explícito | Detecta `pyproject.toml` automaticamente |

**Por que `pyproject.toml` como único arquivo de configuração?**

`ruff`, `mypy` e `pytest` aceitam configuração via `pyproject.toml` — evita proliferação de
`setup.cfg`, `.flake8`, `pytest.ini`, `mypy.ini` no mesmo diretório. Um arquivo para
governar tudo.

**Por que Railway detecta automaticamente?**

Railway identifica projetos Python com `pyproject.toml` + Poetry e executa
`poetry install --no-dev` em produção automaticamente — sem `Dockerfile` ou scripts de
build customizados.

## Consequences

**Positivos:**
- `poetry.lock` garante que dev, CI e Railway usam exatamente as mesmas versões
- `poetry install` em um ambiente novo instala tudo em um comando
- Grupos de dependência (`dev`) não vão para produção automaticamente
- Configuração de linting, type checking e testes no mesmo arquivo

**Negativos / Trade-offs:**
- Poetry precisa ser instalado no ambiente de dev (`pip install poetry` ou via `pipx`)
- `poetry.lock` deve ser commitado — arquivo grande que muda com atualizações de deps
- Curva de aprendizado para devs acostumados com `pip` direto

**Comandos essenciais:**

```bash
poetry install              # instala todas as deps (prod + dev)
poetry install --no-dev     # só produção (Railway usa isso)
poetry add <pacote>         # adiciona dep de produção
poetry add --group dev <p>  # adiciona dep de desenvolvimento
poetry run pytest           # executa comando no virtualenv gerenciado pelo Poetry
poetry update               # atualiza deps dentro das constraints do pyproject.toml
```

## Referências

- `apps/api/pyproject.toml` — arquivo de configuração
- `apps/api/poetry.lock` — lock file (deve ser commitado)
- `ADR-013` — constraint `bcrypt = ">=3.2,<4"` dentro do Poetry