# 005 - TDD Obrigatório: Red → Green → Refactor

**Status:** `accepted`

---

## Context

O projeto é desenvolvido por um dev solo que está aprendendo backend e engenharia de software no processo. Sem testes automatizados, refactors e novas features introduzem regressões silenciosas — especialmente crítico num sistema multi-tenant onde um bug pode vazar dados entre tenants.

Além disso, o TDD é uma das metas de aprendizado explícitas do desenvolvedor — não apenas uma prática de qualidade, mas um objetivo do processo de desenvolvimento.

## Decision

TDD é obrigatório em todos os módulos do backend. O ciclo é:

```
1. Red    → escrever o teste que descreve o comportamento esperado (falha porque o código não existe)
2. Green  → escrever o mínimo de código para o teste passar
3. Refactor → melhorar o código sem quebrar os testes
```

**Regra prática:** sempre mostrar o teste antes da implementação em qualquer sessão de pair programming com o Claude.

### Estrutura de testes

Testes espelham a estrutura de módulos:

```
api/tests/
├── conftest.py                   → fixtures compartilhadas (db_session, http_client, etc.)
├── core/
│   ├── test_security.py
│   └── test_deps.py
├── auth/
│   ├── test_router.py            → testa endpoints HTTP (status codes, response shapes)
│   ├── test_service.py           → testa regras de negócio (mock repository)
│   └── test_repository.py       → testa queries contra banco de teste real
├── professionals/
│   ├── test_model.py
│   ├── test_router.py
│   ├── test_service.py
│   └── test_repository.py
├── clients/
│   └── ...
└── agenda/
    └── ...
```

### Fixtures globais (`tests/conftest.py`)

| Fixture | Responsabilidade |
|---|---|
| `db_session` | Transação por teste com rollback automático — isolamento total |
| `http_client` | `AsyncClient` com `get_db` sobreescrito para a `db_session` de teste; usa `base_url="https://testserver"` (cookies `Secure`) |
| `authenticated_http_client` | `http_client` + header `Authorization: Bearer <jwt>` do `test_professional` |
| `test_professional` | `Professional` real flushed na transação de teste |

### Stack de testes

- `pytest` + `pytest-asyncio` — testes async nativos
- `httpx.AsyncClient` com `ASGITransport` — testa a app FastAPI sem servidor real
- `factory-boy` — factories para criar dados de teste de forma declarativa
- Banco de teste PostgreSQL real — testes de repository rodam contra PostgreSQL, não SQLite

## Rationale

**Por que TDD e não testes após a implementação?**
- Escrever o teste primeiro força clareza sobre o comportamento esperado antes de pensar em como implementar
- O teste que falha (Red) confirma que está testando o que se pensa estar testando
- Evita o viés de escrever testes que passam trivialmente porque o código já existe

**Por que banco PostgreSQL real nos testes (e não SQLite)?**
- SQLite não suporta RLS, `SET LOCAL`, `TIMESTAMPTZ`, `UUID gen_random_uuid()` — todos usados no projeto
- Comportamento idêntico ao de produção — sem surpresas de dialeto SQL
- `pytest-postgresql` ou `docker-compose` provisionam o banco de teste automaticamente

**Por que rollback automático por teste (e não truncate)?**
- Rollback é mais rápido que truncate + reinsert
- Garante isolamento completo entre testes sem estado residual
- Funciona com `SET LOCAL` (scoped à transação) — um commit quebraria o contexto RLS

**Por que testar as 3 camadas separadamente?**
- Testes de repository verificam que as queries ORM geram o SQL correto
- Testes de service verificam regras de negócio sem depender do banco
- Testes de router verificam os contratos HTTP sem conhecer a implementação interna
- Falhas são localizadas: um test_service falhando indica bug no service, não no banco

## Consequences

**Positivos:**
- Regressões detectadas imediatamente — não em produção
- Refactors seguros: se os testes passam, o comportamento externo está preservado
- Documentação executável: os testes descrevem o comportamento esperado do sistema
- Aprendizado acelerado: TDD força entendimento do comportamento antes da implementação

**Negativos / Trade-offs:**
- Velocidade inicial menor — escrever o teste antes é mais lento no curto prazo
- Curva de aprendizado para quem vem do mundo frontend (onde TDD é menos comum)
- Fixtures e setup de banco de teste têm complexidade não trivial (ver ADR-021 para RLS em testes)

## Referências

- `api/tests/conftest.py` — fixtures compartilhadas
- `ADR-021` — estratégia de testes de isolamento RLS
- `domains/core.md` — detalhes das fixtures de teste