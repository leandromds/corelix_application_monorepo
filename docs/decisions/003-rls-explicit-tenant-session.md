# 003 - RLS: Ativação Explícita via TenantSession

**Status:** `accepted`

---

## Context

O sistema usa PostgreSQL Row Level Security (RLS) para isolar dados entre tenants. A questão central era: **onde e como ativar o contexto de tenant** (`SET LOCAL app.current_tenant`) a cada request?

Duas abordagens foram avaliadas:

1. **Middleware automático:** intercepta todo request, extrai o JWT, chama `set_tenant_context()` antes de chegar ao router
2. **Dependency explícita (`TenantSession`):** cada rota declara explicitamente que precisa de sessão com RLS ativado

O sistema tem rotas que **não possuem tenant** — login, registro, webhook do WhatsApp, refresh de token. Um middleware automático precisaria de uma lista de exceções para essas rotas, criando um vetor de bug de segurança: se uma rota nova for esquecida na lista de exceções, ela executaria sem RLS mas com dados de um tenant fantasma ou sem contexto algum.

## Decision

`set_tenant_context()` é chamado **exclusivamente via FastAPI `Depends`**, através da dependência `TenantSession` definida em `core/deps.py`.

```python
# core/deps.py

DbSession             = Annotated[AsyncSession, Depends(get_db)]
# ↑ sessão pura — para rotas públicas (login, register, refresh, webhooks)

CurrentProfessionalId = Annotated[str, Depends(get_current_professional_id)]
# ↑ extrai e valida o JWT — retorna o professional_id como string

TenantSession         = Annotated[AsyncSession, Depends(get_tenant_db)]
# ↑ get_db + JWT + SET LOCAL — para rotas protegidas com isolamento de tenant
```

Internamente, `get_tenant_db` combina `get_db` + `get_current_professional_id` + `set_tenant_context()`:

```python
async def get_tenant_db(
    professional_id: CurrentProfessionalId,
    db: DbSession,
) -> AsyncGenerator[AsyncSession, None]:
    await set_tenant_context(db, professional_id)
    yield db
```

Rotas públicas usam `DbSession`. Rotas protegidas usam `TenantSession`. A escolha é explícita e visível na assinatura de cada endpoint.

## Rationale

**Segurança por padrão:** uma rota sem `TenantSession` simplesmente não ativa RLS. Não há lista de exceções para manter. Se um dev esquecer de usar `TenantSession` em uma rota que deveria ser protegida, o erro é visível — a rota não terá acesso ao JWT e falhará na autenticação.

**Princípio do menor privilégio:** rotas públicas recebem `DbSession` sem contexto de tenant — elas não têm acesso a dados de nenhum tenant. Um middleware automático que falha silenciosamente poderia expor dados.

**Alinhamento com FastAPI idiomático:** o sistema de `Depends` é o mecanismo de composição do FastAPI. Usar `TenantSession` é consistente com como auth, validação e injeção de dependências funcionam no resto do framework.

**Testabilidade:** nos testes, `get_db` é sobreescrito pela fixture `db_session`. Como `TenantSession` usa `get_db` internamente via `Depends`, o override propaga automaticamente — não é necessário nenhum mock adicional para testar rotas com RLS.

## Consequences

**Positivos:**
- Cada rota declara explicitamente seu nível de acesso — auditoria fácil
- Sem listas de exceções para manter
- Testes funcionam automaticamente com o override de `get_db`
- Middlewares globais (rate limiting, audit log) continuam possíveis sem interferir no RLS

**Negativos / Trade-offs:**
- Dev precisa lembrar de usar `TenantSession` em rotas novas — erro de omissão resulta em falta de RLS, não em crash
- Nenhuma proteção automática se um dev usar `DbSession` onde deveria usar `TenantSession`

**Mitigação do risco:** revisão de código + testes de isolamento de RLS por módulo garantem que a barreira está ativa onde deve estar. Ver `ADR-021` para estratégia de testes de RLS.

## Referências

- `core/deps.py` — implementação de `DbSession`, `CurrentProfessionalId`, `TenantSession`
- `core/database.py` — implementação de `set_tenant_context()`
- `ADR-001` — decisão de usar RLS como segunda barreira de isolamento
- `ADR-008` — por que `SET LOCAL` usa f-string sem bind params
- `ADR-021` — estratégia de testes de isolamento RLS