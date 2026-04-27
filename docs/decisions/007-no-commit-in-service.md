# 007 - Nunca `session.commit()` no Service Layer

**Status:** `accepted`

---

## Context

O sistema usa PostgreSQL Row Level Security com `SET LOCAL app.current_tenant = '{uuid}'` para
isolar dados entre tenants. O `SET LOCAL` é uma instrução de configuração **scoped à transação
corrente** — ela é automaticamente revertida quando a transação termina (commit ou rollback).

A questão prática: quem deve chamar `session.commit()`? Se o service layer tiver essa
responsabilidade, um commit prematuro encerraria a transação e silenciosamente desativaria o RLS
para qualquer operação subsequente no mesmo request — sem erro, sem aviso, com vazamento potencial
de dados.

## Decision

**Nunca chamar `session.commit()` no service layer.**

O gerenciamento do ciclo de vida da transação (commit/rollback) é responsabilidade exclusiva
do **router layer**, delegado ao mecanismo de `Depends` do FastAPI via `get_db()`:

```python
# core/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()    # ← commit acontece AQUI, ao final do request
        except Exception:
            await session.rollback()
            raise
```

O service layer usa apenas `session.flush()` quando precisa materializar IDs antes do fim
da transação (ex: criar um registro e usar seu `id` gerado imediatamente em seguida):

```python
# service.py — correto
async def create_client(self, professional_id: UUID, data: ClientCreate) -> Client:
    client = await self.repository.create(professional_id, data)
    await self.session.flush()   # materializa o id — NÃO encerra a transação
    return client

# service.py — ERRADO
async def create_client(self, professional_id: UUID, data: ClientCreate) -> Client:
    client = await self.repository.create(professional_id, data)
    await self.session.commit()  # ← encerra a transação, perde o SET LOCAL do RLS
    return client
```

## Rationale

**Integridade do RLS:**
`SET LOCAL` é garantido apenas dentro da transação onde foi executado. Um `commit()` no meio
do request fecha essa transação. A próxima operação abre uma nova sessão sem o contexto de
tenant — qualquer query subsequente enxergaria dados de todos os tenants (ou nenhum, dependendo
da policy).

**Atomicidade como efeito colateral positivo:**
Com o commit centralizado no `get_db()`, todas as operações de um request são atômicas por
padrão. Se qualquer parte falhar, o rollback desfaz tudo. O service layer não precisa gerenciar
transações parciais.

**Testabilidade:**
Os testes usam `db_session` com rollback automático ao final de cada teste. Se o service fizesse
commit, o rollback do teste não funcionaria — os dados persistiriam entre testes, quebrand o
isolamento.

**Analogia frontend:**
É o equivalente a não chamar `setState()` dentro de uma função utilitária pura — quem controla
o ciclo de vida do estado é o componente (router), não a lógica de negócio (service).

## Consequences

**Positivos:**
- RLS permanece ativo durante todo o request, sem brechas entre operações
- Atomicidade por padrão — sem commits parciais acidentais
- Testes com rollback automático funcionam corretamente
- Service layer mais simples — não precisa raciocinar sobre ciclo de vida de transação

**Negativos / Trade-offs:**
- `flush()` pode ser necessário quando o service precisa do `id` gerado antes do fim do request
- Longa cadeia de operações no service (ex: criar recorrência + N sessões) fica em uma
  única transação grande — aceitável para o volume do MVP
- Dev precisa conhecer a distinção entre `flush()` (materializa no buffer) e `commit()`
  (persiste no banco e encerra transação)

**Regra de ouro:**
> Se você precisou chamar `commit()` no service, provavelmente está na camada errada
> ou precisa repensar a estrutura da operação.

## Referências

- `core/database.py` — implementação de `get_db()` com commit/rollback automático
- `ADR-001` — decisão de usar RLS como segunda barreira de isolamento
- `ADR-003` — TenantSession: como o SET LOCAL é ativado por request
- `ADR-008` — por que SET LOCAL usa f-string (sem bind params)