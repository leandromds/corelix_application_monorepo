# 021 - Isolamento de RLS em Testes via `test_rls_user`

**Status:** `accepted`

---

## Context

O sistema usa PostgreSQL Row Level Security (RLS) para isolar dados entre tenants (ADR-001).
Testes que verificam esse isolamento precisam executar queries como um usuário que **respeita
as policies RLS** — caso contrário, o teste não valida o que pretende.

O problema: o usuário `postgres` (padrão em ambientes de desenvolvimento e CI) possui o
privilege `BYPASSRLS` nativo do PostgreSQL. A documentação do PostgreSQL afirma explicitamente:

> "Superusers and roles with the BYPASSRLS attribute always bypass the row security system."
> `FORCE ROW LEVEL SECURITY` **não afeta** usuários com `BYPASSRLS`.

Resultado prático: qualquer teste que roda como `postgres` nunca é bloqueado pelas policies
RLS — mesmo que a policy esteja mal configurada ou ausente. O teste passaria independentemente
da segurança real.

### Segundo problema: policy com `current_setting` sem flag null-safe

A policy padrão:

```sql
CREATE POLICY tenant_isolation ON clients
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```

Lança `ERROR: unrecognized configuration parameter "app.current_tenant"` quando o contexto
não está definido — por exemplo, em testes de modelo que fazem apenas `INSERT` sem setar
o tenant. O `INSERT ... RETURNING *` do SQLAlchemy é filtrado pelo `USING` da policy, e
com a policy lançando erro, `client.id` fica `None` após o `flush()`.

## Decision

### 1. Role dedicada para testes de isolamento

Criar o role `test_rls_user` no banco de teste — sem `BYPASSRLS`, sem `LOGIN`:

```sql
CREATE ROLE test_rls_user NOLOGIN;
GRANT ALL ON ALL TABLES IN SCHEMA public TO test_rls_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO test_rls_user;
```

### 2. Testes de isolamento usam `SET LOCAL ROLE`

```python
# Dentro de um teste de isolamento (dentro de uma transação)
async def test_tenant_isolation(db_session):
    # Ativa o role sem BYPASSRLS
    await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
    # Define o tenant A
    await db_session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_a_id}'")
    )

    # Query que deveria retornar APENAS dados do tenant A
    result = await db_session.execute(select(Client))
    clients = result.scalars().all()

    # Com test_rls_user (sem BYPASSRLS), a policy é aplicada
    assert all(c.professional_id == tenant_a_id for c in clients)
```

Ambos os `SET LOCAL` são **transaction-scoped** — revertidos automaticamente no rollback
automático da fixture `db_session` ao final do teste.

### 3. Como as políticas RLS chegam ao banco de testes

Este é o ponto mais crítico e frequentemente mal documentado.

O banco de testes é criado via `Base.metadata.create_all(engine)` no `conftest.py` —
**não** via `alembic upgrade head`. Isso significa que as políticas RLS definidas
manualmente na migration `56f1e41b5d4c` **não são aplicadas automaticamente**.

As políticas precisam ser criadas programaticamente no `conftest.py`, em uma fixture
de escopo `session` executada uma única vez por suite de testes:

```python
# tests/conftest.py
@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(settings.TEST_DATABASE_URL)

    async with engine.begin() as conn:
        # 1. Cria todas as tabelas via SQLAlchemy metadata
        await conn.run_sync(Base.metadata.create_all)

        # 2. Aplica as políticas RLS manualmente — não vêm do Alembic
        rls_tables = [
            "clients",
            "availability_slots",
            "blocked_periods",
            "sessions",
            "recurrences",
            "whatsapp_conversations",
        ]
        for table in rls_tables:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(
                f"CREATE POLICY IF NOT EXISTS tenant_isolation ON {table} "
                f"USING (professional_id = "
                f"current_setting('app.current_tenant', TRUE)::uuid)"
            ))

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
```

**Por que programático e não via Alembic no CI?**

Rodar `alembic upgrade head` contra o banco de testes exigiria que o banco de testes
começasse vazio a cada run, e que o Alembic estivesse configurado para apontar para
`TEST_DATABASE_URL`. A abordagem programática é mais simples e explícita — as políticas
ficam visíveis no mesmo arquivo que cria as tabelas.

**Consequência para o CI (`ci.yml`):**

O step de setup do `test_rls_user` no workflow cria apenas o **role**. As políticas
RLS são criadas pelo `conftest.py` ao iniciar a suite de testes — não pelo step de
setup do CI. O `GRANT ALL ON ALL TABLES` no step de CI é um **no-op** nesse momento
(as tabelas ainda não existem) e pode ser removido com segurança. Os grants efetivos
são cobertos pelo `ALTER DEFAULT PRIVILEGES`, que se aplica a tabelas criadas
posteriormente pelo `Base.metadata.create_all`.

### 4. Policy null-safe no banco de testes

```sql
-- Usar current_setting com segundo argumento TRUE (missing_ok)
CREATE POLICY tenant_isolation ON clients
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

O segundo argumento `TRUE` (`missing_ok`) faz `current_setting` retornar `NULL` em vez de
lançar erro quando a variável não está definida. Como `professional_id = NULL` é sempre
`FALSE` no SQL, o comportamento é correto: sem contexto de tenant, nenhuma linha é visível.

Isso permite que testes de modelo (`test_model.py`) façam `INSERT` sem definir o tenant —
o `flush()` do SQLAlchemy funciona corretamente e o `id` é populado.

### 5. Separação de responsabilidades nos testes

| Tipo de teste | Role usada | SET LOCAL tenant? | O que verifica |
|---|---|---|---|
| `test_model.py` | `postgres` (BYPASSRLS) | Não | Estrutura do model, constraints, defaults |
| `test_repository.py` | `postgres` (BYPASSRLS) | Sim (via TenantSession) | Queries ORM corretas |
| `test_isolation.py` | `test_rls_user` | Sim | Isolamento real entre tenants |
| `test_service.py` | `postgres` (BYPASSRLS) | Sim | Regras de negócio |
| `test_router.py` | `postgres` (BYPASSRLS) | Sim (via TenantSession override) | Contratos HTTP |

## Rationale

**Por que `CREATE_ALL` + DDL manual e não `alembic upgrade head` nos testes?**

- Mais rápido: `create_all` é uma operação única em memória; Alembic precisa ler o
  histórico de migrations e aplicá-las em sequência
- Mais explícito: as políticas ficam visíveis no `conftest.py`, junto do setup do banco
- Mais isolado: o banco de testes não precisa de configuração extra de Alembic
- **Risco:** se uma migration futura mudar uma policy (ex: adicionar tabela nova com RLS),
  o `conftest.py` precisa ser atualizado manualmente — não é automático. Mitigação:
  manter a lista de tabelas RLS em `conftest.py` sincronizada com a lista em `ADR-001`.

**Por que não usar `FORCE ROW LEVEL SECURITY`?**

`FORCE ROW LEVEL SECURITY` obriga a policy mesmo para o dono da tabela — mas **ainda não
afeta usuários com `BYPASSRLS`**. O usuário `postgres` é superuser e tem `BYPASSRLS`
implicitamente. Alterar isso exigiria mudar o superuser do banco — impraticável e perigoso.

**Por que `SET LOCAL ROLE` (e não `SET ROLE`)?**

`SET LOCAL` é transaction-scoped — reverte automaticamente com o rollback do teste.
`SET ROLE` persistiria na sessão, afetando testes subsequentes que reusam a mesma conexão
do pool.

**Por que role `NOLOGIN`?**

O `test_rls_user` não precisa fazer login no banco — ele é adotado via `SET LOCAL ROLE`
dentro de uma sessão já autenticada como `postgres`. `NOLOGIN` previne uso não intencional
como credencial de conexão direta.

**Por que policy `missing_ok=TRUE` e não policy separada para testes?**

Uma policy separada para testes diverge do comportamento de produção — você estaria testando
uma policy diferente da que roda em produção. `current_setting('app.current_tenant', TRUE)`
é igualmente seguro: sem contexto, nenhuma linha é retornada (não um erro). O comportamento
de produção é o mesmo — `TenantSession` sempre define o contexto antes de qualquer query.

## Consequences

**Positivos:**
- Testes de isolamento verificam o RLS real — sem falsos positivos
- Testes de modelo funcionam sem setar tenant (sem erro da policy)
- `SET LOCAL` é automaticamente revertido pelo rollback da fixture — sem estado residual
- O banco de teste usa a mesma policy do banco de produção (apenas com `missing_ok=TRUE`)

**Negativos / Trade-offs:**
- Setup adicional no banco de teste: `CREATE ROLE test_rls_user` + `GRANT`s
- Testes de isolamento são mais complexos — exigem dois `SET LOCAL` em sequência
- Se `test_rls_user` não for criado, os testes de isolamento falham com erro de role — não silenciosamente

**Setup necessário no banco de teste (one-time, feito uma vez):**

```sql
-- Executar UMA VEZ ao criar o banco de teste (via docker ou CI setup step)
-- O GRANT ALL ON ALL TABLES é no-op aqui (tabelas ainda não existem),
-- mas é inofensivo. O que realmente importa é o ALTER DEFAULT PRIVILEGES.
CREATE ROLE test_rls_user NOLOGIN;
GRANT USAGE ON SCHEMA public TO test_rls_user;
-- Para tabelas que serão criadas pelo Base.metadata.create_all:
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO test_rls_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO test_rls_user;
```

**As políticas RLS são criadas pelo `conftest.py`** (fixture `test_engine`, escopo
`session`) — não por este setup manual nem pelo `ci.yml`. Ver seção "Como as
políticas RLS chegam ao banco de testes" acima.

## Referências

- `api/tests/conftest.py` — fixture `db_session` com rollback automático
- `ADR-001` — decisão de usar RLS como segunda barreira de isolamento
- `ADR-003` — TenantSession: como `SET LOCAL` é ativado em produção
- `ADR-008` — por que `SET LOCAL` usa f-string sem bind params